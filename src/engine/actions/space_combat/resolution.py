from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from src.engine.actions.movement import OpenWindowEvent
from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    EngineContext,
    ValidationResult,
    make_command_candidates_for_all_players,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import (
    CombatRoll,
    GameState,
    HitAssignmentContext,
    HitSource,
    SpaceCombatStep,
    TacticalActionStep,
    Window,
)
from src.engine.core.windows import CloseWindowEvent
from src.engine.units.sustain_damage import SustainDamageEvent

from .afb_and_retreat import (
    AdvanceToRetreatStepEvent,
    EndAntiFighterBarrageStepEvent,
    ResolvePendingRetreatsEvent,
)
from .shared import (
    active_ship_owners,
    get_active_system_id,
    has_finished_assigning_hits,
    needs_to_assign_hits,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class InvalidCombatRollError(ValueError):
    pass


def make_combat_roll(unit, dice_roller) -> CombatRoll:
    value = dice_roller.roll(num_dice=1)[0]
    if unit.stats.combat is None:
        raise InvalidCombatRollError
    return CombatRoll(unit_id=unit.unit_id, value=value, hit=value >= unit.stats.combat)


class RollDiceForUnitEvent(Event):
    def __init__(self, unit_id: int, combat_rolls: tuple[CombatRoll, ...]) -> None:
        self.unit_id = unit_id
        self.combat_rolls = combat_rolls

    def apply(self, previous_state: GameState) -> GameState:
        for combat_roll in self.combat_rolls:
            previous_state = previous_state.register_combat_roll(combat_roll)
        return previous_state

    def __repr__(self) -> str:
        return f"RollDiceForUnit:{self.unit_id}:{self.combat_rolls}"


class MakeCombatRollsCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "MakeCombatRollsCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.MAKE_COMBAT_ROLLS}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        space_combat_context = state.turn_context.get_space_combat_context()
        if space_combat_context.step != SpaceCombatStep.ROLL_DICE:
            return ValidationResult(
                is_valid=False,
                info="Can only make combat rolls during roll dice step.",
            )
        if command.actor not in (space_combat_context.attacker, space_combat_context.defender):
            return ValidationResult(
                is_valid=False,
                info="You are not participating in this combat.",
            )
        if space_combat_context.get_combat_rolls_for_player(command.actor):
            return ValidationResult(
                is_valid=False,
                info="Combat rolls have already been made for this player.",
            )
        if (
            command.actor != space_combat_context.attacker
            and not space_combat_context.get_combat_rolls_for_player(space_combat_context.attacker)
        ):
            return ValidationResult(
                is_valid=False,
                info="Attacker must roll before defender.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        units = state.get_units_in_system(get_active_system_id(state))
        ordered_units = sorted(units, key=lambda unit: (unit.stats.combat or 0, unit.unit_id))
        return [
            RollDiceForUnitEvent(
                unit_id=unit.unit_id,
                combat_rolls=tuple(
                    make_combat_roll(unit=unit, dice_roller=engine_context.dice_roller)
                    for _ in range(unit.stats.num_dice)
                ),
            )
            for unit in ordered_units
            if unit.stats.combat is not None and unit.is_ship and unit.owner_name == command.actor
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if state.turn_context.space_combat_context is None:
            return []
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=MakeCombatRollsCommandRule,
        )


class AdvanceToAssignHitsStepEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            replace(
                previous_state.turn_context.get_space_combat_context(),
                step=SpaceCombatStep.ASSIGN_HITS,
            ),
        )

    def __repr__(self) -> str:
        return "AdvanceToAssignHitsStepEvent"


class SetHitsAssigneeEvent(Event):
    def __init__(self, player_name: str | None, num_hits: int) -> None:
        self.player_name = player_name
        self.num_hits = num_hits

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_hit_context(
            HitAssignmentContext(
                assignee=self.player_name,
                source=HitSource.SPACE_COMBAT,
                hits_remaining=self.num_hits,
                assigned_hits=frozenset({}),
                system_id=get_active_system_id(previous_state),
            )
            if self.player_name is not None
            else None,
        )

    def __repr__(self) -> str:
        return f"SetHitsAssigneeEvent:{self.player_name}"


class OpenBeforeAssignHitsWindowEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        return (
            [OpenWindowEvent(Window.BEFORE_ASSIGNING_HITS)]
            if state.turn_context.hit_assignment_context is not None
            else []
        )

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {SetHitsAssigneeEvent}


class AdvanceToAssignHitsStepEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {RollDiceForUnitEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        combat_context = state.turn_context.get_space_combat_context()
        attacker_rolls = combat_context.get_combat_rolls_for_player(combat_context.attacker)
        defender_rolls = combat_context.get_combat_rolls_for_player(combat_context.defender)
        attacker_rolled_unit_ids = {roll.unit_id for roll in attacker_rolls}
        defender_rolled_unit_ids = {roll.unit_id for roll in defender_rolls}
        if not (
            {
                ship.unit_id
                for ship in state.get_ships_in_system(
                    get_active_system_id(state),
                    player_name=combat_context.attacker,
                )
            }
            - attacker_rolled_unit_ids
        ) and not (
            {
                ship.unit_id
                for ship in state.get_ships_in_system(
                    get_active_system_id(state),
                    player_name=combat_context.defender,
                )
            }
            - defender_rolled_unit_ids
        ):
            initial_assignee, combat_roller = None, ""
            if needs_to_assign_hits(state, combat_context.attacker):
                initial_assignee, combat_roller = combat_context.attacker, combat_context.defender
            elif needs_to_assign_hits(state, combat_context.defender):
                initial_assignee, combat_roller = combat_context.defender, combat_context.attacker
            return [
                AdvanceToAssignHitsStepEvent(),
                SetHitsAssigneeEvent(
                    initial_assignee,
                    num_hits=combat_context.total_hits_for_player(combat_roller)
                    if initial_assignee is not None
                    else 0,
                ),
            ]
        return []


@dataclass(frozen=True)
class AssignHitCommand(Command):
    unit_id: int


class AssignHitEvent(Event):
    def __init__(self, unit_id: int, player_name: str) -> None:
        self.unit_id = unit_id
        self.player_name = player_name

    def __repr__(self) -> str:
        return f"AssignHitEvent(unit_id={self.unit_id},player_name={self.player_name})"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_hit_context(
            previous_state.turn_context.get_hit_assignment_context().assign_hit(
                unit_id=self.unit_id,
            ),
        )


def _legal_hit_assignment(state: GameState, command: AssignHitCommand) -> ValidationResult:
    hit_context = state.turn_context.get_hit_assignment_context()
    unit = state.get_unit_from_id(unit_id=command.unit_id)
    if not hit_context.is_valid_target(unit):
        return ValidationResult(
            is_valid=False,
            info=f"Unit {unit.unit_id} is not a valid target for this hit.",
        )
    if unit.owner_name != command.actor:
        return ValidationResult(
            is_valid=False,
            info="You can only assign hits to your own units.",
        )
    return ValidationResult(is_valid=True)


class AssignHitCommandRule(CommandRule[AssignHitCommand]):
    def __repr__(self) -> str:
        return "AssignHitCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.ASSIGN_HIT}

    def validate_legality(self, state: GameState, command: AssignHitCommand) -> ValidationResult:
        space_combat_context = state.turn_context.get_space_combat_context()
        if space_combat_context.step != SpaceCombatStep.ASSIGN_HITS:
            return ValidationResult(
                is_valid=False,
                info="Can only assign hits during assign hit step.",
            )
        legal_assignment_result = _legal_hit_assignment(state=state, command=command)
        if not legal_assignment_result.is_valid:
            return legal_assignment_result
        if not needs_to_assign_hits(
            state=state,
            player_name=command.actor,
        ) or has_finished_assigning_hits(state=state, player_name=command.actor):
            return ValidationResult(is_valid=False, info="No more hits to assign.")
        if (
            command.actor == space_combat_context.defender
            and needs_to_assign_hits(state=state, player_name=space_combat_context.attacker)
            and not has_finished_assigning_hits(
                state=state,
                player_name=space_combat_context.attacker,
            )
        ):
            return ValidationResult(is_valid=False, info="Attacker must assign all hits first.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: AssignHitCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [AssignHitEvent(unit_id=command.unit_id, player_name=command.actor)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[AssignHitCommand]:
        if (
            state.turn_context.space_combat_context is None
            or state.turn_context.hit_assignment_context is None
        ):
            return []
        if state.turn_context.get_space_combat_context().step != SpaceCombatStep.ASSIGN_HITS:
            return []
        return [
            AssignHitCommand(
                actor=unit.owner_name,
                command_type=CommandType.ASSIGN_HIT,
                unit_id=unit.unit_id,
            )
            for unit in state.units
            if unit.system_id is not None
        ]


class PassBeforeAssignHitsCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassBeforeAssignHitsCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_BEFORE_ASSIGN_HITS}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.turn_context.space_combat_context is None:
            return ValidationResult(
                is_valid=False,
                info="Can only pass before assigning hits during space combat.",
            )
        if command.actor != state.turn_context.get_hit_assignment_context().assignee:
            return ValidationResult(
                is_valid=False,
                info="This is not your assign hits window to pass.",
            )
        if not state.window_context.is_window_active(Window.BEFORE_ASSIGNING_HITS):
            return ValidationResult(
                is_valid=False,
                info="Can only pass before assigning hits.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return [CloseWindowEvent(Window.BEFORE_ASSIGNING_HITS)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if (
            state.turn_context.space_combat_context is None
            or state.turn_context.hit_assignment_context is None
        ):
            return []
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=PassBeforeAssignHitsCommandRule,
        )


class DestroyUnitEvent(Event):
    def __init__(self, unit_id: int) -> None:
        self.unit_id = unit_id

    def __repr__(self) -> str:
        return f"DestroyUnitEvent(unit_id={self.unit_id})"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.remove_unit(unit_id=self.unit_id)


class DestroyUnitWhenAssignedHitEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del state
        if not isinstance(event, AssignHitEvent):
            return []
        return [DestroyUnitEvent(event.unit_id)]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {AssignHitEvent}


class SwitchAssigneeWhenFinishedAssigningEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        combat_context = state.turn_context.get_space_combat_context()
        hit_context = state.turn_context.get_hit_assignment_context()
        if combat_context.step != SpaceCombatStep.ASSIGN_HITS:
            return []
        if hit_context.assignee == combat_context.attacker and has_finished_assigning_hits(
            state,
            combat_context.attacker,
        ):
            return [
                SetHitsAssigneeEvent(
                    player_name=combat_context.defender,
                    num_hits=combat_context.total_hits_for_player(combat_context.defender),
                )
                if needs_to_assign_hits(state, combat_context.defender)
                else SetHitsAssigneeEvent(player_name=None, num_hits=0),
            ]
        if hit_context.assignee == combat_context.defender and has_finished_assigning_hits(
            state,
            combat_context.defender,
        ):
            return [SetHitsAssigneeEvent(player_name=None, num_hits=0)]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {DestroyUnitEvent, SustainDamageEvent}


class AdvanceToRetreatStepEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        combat_context = state.turn_context.get_space_combat_context()
        both_players_have_ships = all(
            state.get_ships_in_system(get_active_system_id(state), player_name)
            for player_name in [combat_context.attacker, combat_context.defender]
        )
        should_advance = False
        if isinstance(event, SetHitsAssigneeEvent):
            should_advance = event.player_name is None and both_players_have_ships
        else:
            should_advance = both_players_have_ships and all(
                (
                    not needs_to_assign_hits(state=state, player_name=player_name)
                    or has_finished_assigning_hits(state=state, player_name=player_name)
                )
                for player_name in [combat_context.attacker, combat_context.defender]
            )
        if not should_advance:
            return []
        if combat_context.declared_retreat_name is None:
            return [OpenWindowEvent(Window.END_OF_SPACE_COMBAT_ROUND)]
        return [AdvanceToRetreatStepEvent()]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {DestroyUnitEvent, SetHitsAssigneeEvent, SustainDamageEvent}


class EndSpaceCombatEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {
            DestroyUnitEvent,
            EndAntiFighterBarrageStepEvent,
            ResolvePendingRetreatsEvent,
            AssignHitEvent,
            SustainDamageEvent,
        }

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if state.turn_context.tactical_action_step != TacticalActionStep.SPACE_COMBAT:
            return []
        combat_context = state.turn_context.get_space_combat_context()
        if len(active_ship_owners(state)) <= 1 and all(
            (
                not needs_to_assign_hits(state=state, player_name=player_name)
                or has_finished_assigning_hits(state=state, player_name=player_name)
            )
            for player_name in [combat_context.attacker, combat_context.defender]
        ):
            return [
                AssignCombatWinnerEvent(),
                OpenWindowEvent(window=Window.END_OF_SPACE_COMBAT),
                OpenWindowEvent(window=Window.END_OF_SPACE_COMBAT_ROUND),
            ]
        return []


class CannotInferCombatWinnerError(ValueError):
    pass


class AssignCombatWinnerEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        remaining_ships_owners = {
            ship.owner_name
            for ship in previous_state.get_ships_in_system(
                system_id=get_active_system_id(previous_state),
            )
        }
        if len(remaining_ships_owners) > 1:
            raise CannotInferCombatWinnerError
        if len(remaining_ships_owners) == 0:
            return previous_state.set_space_combat_context(
                previous_state.turn_context.get_space_combat_context().set_winner(None),
            )
        if len(remaining_ships_owners) == 1:
            return previous_state.set_space_combat_context(
                previous_state.turn_context.get_space_combat_context().set_winner(
                    remaining_ships_owners.pop(),
                ),
            )
        raise CannotInferCombatWinnerError

    def __repr__(self) -> str:
        return "AssignCombatWinnerEvent"


class CloseBeforeAssignHitsWindowIfAllHitsCancelledEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        context = state.turn_context.hit_assignment_context
        if context is not None and has_finished_assigning_hits(
            state=state,
            player_name=context.assignee,
        ):
            return [CloseWindowEvent(Window.BEFORE_ASSIGNING_HITS)]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {SustainDamageEvent}
