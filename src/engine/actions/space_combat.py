from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable, Final

from src.engine.actions.movement import (
    AddMoveToPendingEvent,
    EndMovementStepEvent,
    OpenWindowEvent,
    resolve_pending_moves,
)
from src.engine.actions.tactical_action import (
    AdvanceToInvasionStepEvent,
    AdvanceToSpaceCombatStepEvent,
)
from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    EngineContext,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import (
    Ability,
    CombatRoll,
    GameState,
    InvalidRetreatError,
    SpaceCombatContext,
    SpaceCombatParticipant,
    SpaceCombatStep,
    TacticalActionStep,
    Window,
)
from src.engine.core.player import CommandTokenPool, Player
from src.engine.core.windows import CloseWindowEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.dice_roller import DiceRoller
    from src.engine.core.system import System
    from src.engine.units.units import Unit


START_OF_COMBAT_ROUND_WINDOWS: list[Window] = [
    Window.START_OF_SPACE_COMBAT,
    Window.START_OF_FIRST_ROUND_OF_SPACE_COMBAT,
    Window.START_OF_SPACE_COMBAT_ROUND,
]


class StartSpaceCombatEvent(Event):
    def __repr__(self) -> str:
        return "StartSpaceCombatEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            space_combat_context=SpaceCombatContext(
                step=SpaceCombatStep.ANTI_FIGHTER_BARRAGE,
                round_number=1,
                attacker=previous_state.active_player,
                defender=previous_state.get_defender_in_system(
                    system_id=previous_state.get_active_system().id,
                ),
            ),
        )


class OpenStartOfSpaceCombatWindowEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {AdvanceToSpaceCombatStepEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event, state
        return [
            StartSpaceCombatEvent(),
        ] + [OpenWindowEvent(window=window) for window in START_OF_COMBAT_ROUND_WINDOWS]


class SkipSpaceCombatIfOnlyOnePlayerHasShips(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {EndMovementStepEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if (
            len(
                {
                    unit.owner_name
                    for unit in state.get_ships_in_system(state.get_active_system().id)
                },
            )
            <= 1
        ):
            return [AdvanceToInvasionStepEvent()]
        return [AdvanceToSpaceCombatStepEvent()]


class EndSpaceCombatCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "EndSpaceCombatCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_SPACE_COMBAT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only active player can end space combat.")
        if state.turn_context.tactical_action_step != TacticalActionStep.SPACE_COMBAT:
            return ValidationResult(
                is_valid=False,
                info="Can only end space combat during space combat window.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> list[Event]:
        del state, command, engine_context
        return [AdvanceToInvasionStepEvent()]


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
        if combat_context.step != SpaceCombatStep.ASSIGN_HITS:
            return []
        if (
            combat_context.current_hits_assignee == combat_context.attacker
            and has_finished_assigning_hits(state, combat_context.attacker)
        ):
            return [
                SetHitsAssigneeEvent(
                    player=combat_context.defender
                    if not has_finished_assigning_hits(state, combat_context.defender)
                    else None,
                ),
            ]
        if (
            combat_context.current_hits_assignee == combat_context.defender
            and has_finished_assigning_hits(state, combat_context.defender)
        ):
            return [SetHitsAssigneeEvent(player=None)]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {DestroyUnitEvent}


def has_finished_assigning_hits(state: GameState, player: Player) -> bool:
    combat_context = state.turn_context.get_space_combat_context()
    return (
        combat_context.unassigned_hits_for_player(player) == 0
    ) or not state.get_ships_in_system(system_id=state.get_active_system().id, player=player)


class AdvanceToRetreatStepEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        combat_context = state.turn_context.get_space_combat_context()
        if all(
            has_finished_assigning_hits(state=state, player=player)
            and state.get_ships_in_system(state.get_active_system().id, player)
            for player in [combat_context.attacker, combat_context.defender]
        ):
            return [AdvanceToRetreatStepEvent()]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {DestroyUnitEvent}


class EndSpaceCombatEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {DestroyUnitEvent, EndAntiFighterBarrageStepEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if state.turn_context.tactical_action_step != TacticalActionStep.SPACE_COMBAT:
            return []
        if (
            len(
                {
                    ship.owner_name
                    for ship in state.get_ships_in_system(state.get_active_system().id)
                },
            )
            <= 1
        ):
            return [
                OpenWindowEvent(window=Window.END_OF_SPACE_COMBAT),
                OpenWindowEvent(window=Window.END_OF_SPACE_COMBAT_ROUND),
            ]
        return []


class PassStartOfCombatWindowCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassStartOfCombatWindowCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_START_OF_COMBAT_ROUND}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [PassStartOfCombatWindowEvent(player=command.actor)]


class PassStartOfCombatWindowEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def __repr__(self) -> str:
        return f"PassStartOfCombatWindowEvent:{self.player}"

    def apply(self, previous_state: GameState) -> GameState:
        active_state = previous_state
        for window in previous_state.window_context.active_windows:
            if window in START_OF_COMBAT_ROUND_WINDOWS:
                active_state = active_state.pass_on_window_for_player(
                    player=self.player,
                    window=window,
                )
        return active_state


class CloseStartOfSpaceCombatRoundWindowsEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {PassStartOfCombatWindowEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if all(
            state.window_context.player_has_passed_on_window(
                player,
                window=Window.START_OF_SPACE_COMBAT_ROUND,
            )
            for player in state.players
        ):
            return [
                CloseWindowEvent(window=window)
                for window in state.window_context.active_windows
                if window in START_OF_COMBAT_ROUND_WINDOWS
            ] + [OpenWindowEvent(window=Window.ANTI_FIGHTER_BARRAGE)]
        return []


class ResolveAntiFighterBarrageEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.use_ability_for_player(
            player=self.player,
            ability=Ability.ANTI_FIGHTER_BARRAGE,
        )

    def __repr__(self) -> str:
        return f"ResolveAntiFighterBarrageEvent:{self.player}"


class PassAntiFighterBarrageEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.pass_on_window_for_player(
            player=self.player,
            window=Window.ANTI_FIGHTER_BARRAGE,
        )

    def __repr__(self) -> str:
        return f"PassAntiFighterBarrageEvent:{self.player}"


class UseAntiFighterBarrageCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "UseAntiFighterBarrageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_ANTI_FIGHTER_BARRAGE}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.turn_context.space_combat_context is None:
            return ValidationResult(
                is_valid=False,
                info="Anti-fighter barrage only valid during space combat.",
            )
        if (
            state.turn_context.space_combat_context.step != SpaceCombatStep.ANTI_FIGHTER_BARRAGE
            or state.turn_context.space_combat_context.round_number > 1
        ):
            return ValidationResult(
                is_valid=False,
                info="AFB is only usable during AFB step of first round of combat.",
            )
        if not state.player_may_resolve_afb_in_system(
            player=command.actor,
            system_id=state.get_active_system().id,
        ):
            return ValidationResult(
                is_valid=False,
                info="Player has no eligible units with ANTI-FIGHTER BARRAGE in the system.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [ResolveAntiFighterBarrageEvent(player=command.actor)]


class PassAntiFighterBarrageCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassAntiFighterBarrageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_ANTI_FIGHTER_BARRAGE}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [PassAntiFighterBarrageEvent(player=command.actor)]


class EndAntiFighterBarrageStepEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            replace(
                previous_state.turn_context.get_space_combat_context(),
                step=SpaceCombatStep.ANNOUNCE_RETREATS,
            ),
        )

    def __repr__(self) -> str:
        return "EndAntiFighterBarrageStepEvent"


class CloseAntiFighterBarrageWindowEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolveAntiFighterBarrageEvent, PassAntiFighterBarrageEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if all(
            not state.player_may_resolve_afb_in_system(
                player=player,
                system_id=state.get_active_system().id,
            )
            for player in [
                state.turn_context.get_space_combat_context().attacker,
                state.turn_context.get_space_combat_context().defender,
            ]
        ):
            return [CloseWindowEvent(Window.ANTI_FIGHTER_BARRAGE), EndAntiFighterBarrageStepEvent()]
        return []


class AnnounceRetreatEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().announce_retreat(
                player=self.player,
                is_retreating=True,
            ),
        )

    def __repr__(self) -> str:
        return "AnnounceRetreatEvent"


class PassAnnounceRetreatEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().announce_retreat(
                player=self.player,
                is_retreating=False,
            ),
        )

    def __repr__(self) -> str:
        return "PassAnnounceRetreatEvent"


def _is_eligible_retreat_system_for_player(
    system: System,
    state: GameState,
    player: Player,
) -> bool:
    if not state.get_active_system().is_adjacent_to(system):
        return False
    if any(
        ship.owner_name != player.name for ship in state.get_ships_in_system(system_id=system.id)
    ):
        return False
    return any(
        unit.owner_name == player.name for unit in state.get_units_in_system(system.id)
    ) or any(planet.controller == player for planet in system.planets)


def _check_for_eligible_retreat_system(state: GameState, player: Player) -> ValidationResult:
    systems = state.galaxy.get_adjacent_systems(system_id=state.get_active_system().id)
    for system in systems:
        if _is_eligible_retreat_system_for_player(system, state=state, player=player):
            return ValidationResult(is_valid=True)
    return ValidationResult(is_valid=False, info="No legal retreat system found.")


def _check_declaration_ordering(
    state: GameState,
    command: Command,
    space_combat_context: SpaceCombatContext,
) -> ValidationResult:
    participant = state.turn_context.get_space_combat_context().get_participant_by_player(
        player=command.actor,
    )
    if (
        space_combat_context.retreat_declaration.get_declaration_by_participant(
            participant=participant,
        )
        is not None
    ):
        return ValidationResult(
            is_valid=False,
            info="This player has already passed/declared retreat this round.",
        )
    if participant == SpaceCombatParticipant.ATTACKER:
        if space_combat_context.retreat_declaration.defender_has_declared is None:
            return ValidationResult(
                is_valid=False,
                info="Must allow defender to declare retreats first.",
            )
        if (
            space_combat_context.retreat_declaration.defender_has_declared
            and command.command_type == CommandType.ANNOUNCE_RETREAT
        ):
            return ValidationResult(
                is_valid=False,
                info="Defender has already announced a retreat, attacker cannot.",
            )
    return ValidationResult(is_valid=True)


EventFactoryByPlayer = Callable[[Player], Event]


class AnnounceRetreatCommandRule(CommandRule[Command]):
    _COMMAND_TO_EVENT_FACTORY: Final[dict[CommandType, EventFactoryByPlayer]] = {
        CommandType.ANNOUNCE_RETREAT: AnnounceRetreatEvent,
        CommandType.PASS_ANNOUNCE_RETREAT: PassAnnounceRetreatEvent,
    }

    @classmethod
    def _make_event_from_command(cls, command_type: CommandType, player: Player) -> Event:
        return cls._COMMAND_TO_EVENT_FACTORY[command_type](player)

    def __repr__(self) -> str:
        return "AnnounceRetreatCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.ANNOUNCE_RETREAT, CommandType.PASS_ANNOUNCE_RETREAT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.turn_context.get_space_combat_context().step != SpaceCombatStep.ANNOUNCE_RETREATS:
            return ValidationResult(
                is_valid=False,
                info="Can only announce retreats in announce retreats step.",
            )
        space_combat_context = state.turn_context.get_space_combat_context()
        if command.actor not in (space_combat_context.attacker, space_combat_context.defender):
            return ValidationResult(
                is_valid=False,
                info="You are not participating in this combat.",
            )
        result = _check_declaration_ordering(
            state=state,
            command=command,
            space_combat_context=space_combat_context,
        )
        if not result.is_valid:
            return result

        if command.command_type == CommandType.PASS_ANNOUNCE_RETREAT:
            return ValidationResult(is_valid=True)

        return _check_for_eligible_retreat_system(state=state, player=command.actor)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [
            self._make_event_from_command(command_type=command.command_type, player=command.actor),
        ]


class AdvanceToRollDiceStepEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            replace(
                previous_state.turn_context.get_space_combat_context(),
                step=SpaceCombatStep.ROLL_DICE,
            ),
        )

    def __repr__(self) -> str:
        return "AdvanceToRollDiceStepEvent"


class AdvanceToRetreatStepEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            replace(
                previous_state.turn_context.get_space_combat_context(),
                step=SpaceCombatStep.RETREAT,
            ),
        )

    def __repr__(self) -> str:
        return "AdvanceToRetreatStepEvent"


class AdvanceToRollDiceStepEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        combat_context = state.turn_context.get_space_combat_context()
        if (
            combat_context.declared_retreat is not None
            or combat_context.retreat_declaration.both_players_have_responded
        ):
            return [AdvanceToRollDiceStepEvent()]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {PassAnnounceRetreatEvent, AnnounceRetreatEvent}


class InvalidCombatRollError(ValueError):
    pass


def make_combat_roll(unit: Unit, dice_roller: DiceRoller) -> CombatRoll:
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
        units = state.get_units_in_system(state.get_active_system().id)
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
            if unit.stats.combat is not None
            and unit.is_ship
            and unit.owner_name == command.actor.name
        ]


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
    def __init__(self, player: Player | None) -> None:
        self.player = player

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().set_hits_assignee(self.player),
        )

    def __repr__(self) -> str:
        return "SetHitsAssigneeEvent"


class OpenBeforeAssignHitsWindowEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        return (
            [OpenWindowEvent(Window.BEFORE_ASSIGNING_HITS)]
            if state.turn_context.get_space_combat_context().current_hits_assignee is not None
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
                    state.get_active_system().id,
                    player=combat_context.attacker,
                )
            }
            - attacker_rolled_unit_ids
        ) and not (
            {
                ship.unit_id
                for ship in state.get_ships_in_system(
                    state.get_active_system().id,
                    player=combat_context.defender,
                )
            }
            - defender_rolled_unit_ids
        ):
            initial_assignee = None
            if not has_finished_assigning_hits(state, combat_context.attacker):
                initial_assignee = combat_context.attacker
            elif not has_finished_assigning_hits(state, combat_context.defender):
                initial_assignee = combat_context.defender

            return [AdvanceToAssignHitsStepEvent(), SetHitsAssigneeEvent(initial_assignee)]
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
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().assign_hit(
                unit_id=self.unit_id,
                player=previous_state.get_player(self.player_name),
            ),
        )


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
        unit = state.get_unit_from_id(unit_id=command.unit_id)
        if unit.system_id != state.get_active_system().id:
            return ValidationResult(
                is_valid=False,
                info=f"Ship {unit.unit_id} is not in the active system.",
            )
        if unit.owner_name != command.actor.name:
            return ValidationResult(
                is_valid=False,
                info="You can only assign hits to your own units.",
            )
        if has_finished_assigning_hits(state=state, player=command.actor):
            return ValidationResult(is_valid=False, info="No more hits to assign.")
        if command.actor == space_combat_context.defender and not has_finished_assigning_hits(
            state=state,
            player=space_combat_context.attacker,
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
        return [AssignHitEvent(unit_id=command.unit_id, player_name=command.actor.name)]


class PassBeforeAssignHitsCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassBeforeAssignHitsCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_BEFORE_ASSIGN_HITS}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if command.actor != state.turn_context.get_space_combat_context().current_hits_assignee:
            return ValidationResult(
                is_valid=False,
                info="This is not your assign hits window to pass.",
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


class SustainDamageCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "SustainDamageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_SUSTAIN_DAMAGE}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        # TODO: Proper sustain damage logic
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return []


@dataclass(frozen=True)
class RetreatShipCommand(Command):
    ship_id: int
    to_system_id: int
    transported_unit_ids: frozenset[int] = frozenset()


class RetreatShipCommandRule(CommandRule[RetreatShipCommand]):
    def __repr__(self) -> str:
        return "RetreatShip"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.RETREAT_SHIP}

    def validate_legality(self, state: GameState, command: RetreatShipCommand) -> ValidationResult:
        context = state.turn_context.get_space_combat_context()
        if context.step != SpaceCombatStep.RETREAT:
            return ValidationResult(
                is_valid=False,
                info="Can only retreat during the retreat step.",
            )
        if context.declared_retreat != command.actor:
            return ValidationResult(
                is_valid=False,
                info="Only the player who declared may retreat.",
            )
        if not _is_eligible_retreat_system_for_player(
            system=state.galaxy.get_system(command.to_system_id),
            state=state,
            player=command.actor,
        ):
            return ValidationResult(
                is_valid=False,
                info="System is not eligible for retreat: must contain one or more of that player's"
                " units, a planet they control, or both, as well as no ships controlled by another "
                "player.",
            )
        ship = state.get_ship_from_id(ship_id=command.ship_id)
        if ship.system_id != state.get_active_system().id:
            return ValidationResult(
                is_valid=False,
                info=f"{command.ship_id} is not in the active system.",
            )
        if ship.stats.move is None:
            return ValidationResult(
                is_valid=False,
                info=f"{command.ship_id} cannot move on its own.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: RetreatShipCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [
            AddMoveToPendingEvent(
                ship_id=command.ship_id,
                to_system_id=command.to_system_id,
                transported_unit_ids=command.transported_unit_ids,
            ),
        ]


def resolve_pending_retreats(previous_state: GameState) -> GameState:
    destination_systems = {move.to_system_id for move in previous_state.turn_context.pending_moves}
    if len(destination_systems) != 1:
        raise InvalidRetreatError
    new_state = resolve_pending_moves(previous_state=previous_state)
    return replace(
        new_state,
        turn_context=new_state.turn_context.set_retreat_system_id(destination_systems.pop()),
    )


class ResolvePendingRetreatsEvent(Event):
    def __repr__(self) -> str:
        return "ResolvePendingRetreatsEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return resolve_pending_retreats(previous_state=previous_state)


class EndRetreatCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "RetreatShip"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_RETREAT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.turn_context.get_space_combat_context().step != SpaceCombatStep.RETREAT:
            return ValidationResult(
                is_valid=False,
                info="Can only retreat during the retreat step.",
            )
        if state.turn_context.get_space_combat_context().declared_retreat != command.actor:
            return ValidationResult(
                is_valid=False,
                info="Only the retreating player may resolve retreats.",
            )
        ships_in_active_system_with_move_value = {
            ship.unit_id
            for ship in state.get_ships_in_system(
                system_id=state.get_active_system().id,
                player=command.actor,
            )
            if ship.stats.move is not None
        }
        pending_retreats = {move.ship_id for move in state.turn_context.pending_moves}
        if len(ships_in_active_system_with_move_value - pending_retreats) > 0:
            return ValidationResult(
                is_valid=False,
                info="You must retreat all ships with a move value.",
            )

        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return [ResolvePendingRetreatsEvent()]


class RemoveUnitEvent(Event):
    def __init__(self, unit_id: int) -> None:
        self.unit_id = unit_id

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.remove_unit(self.unit_id)

    def __repr__(self) -> str:
        return f"RemoveUnitEvent:{self.unit_id}"


class RemoveAbandonedFightersAndGroundForcesEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        abandoned_units = state.get_units_in_space_area_of_system(
            system_id=state.get_active_system().id,
            player=state.turn_context.get_space_combat_context().declared_retreat,
        )
        return [RemoveUnitEvent(unit_id=unit.unit_id) for unit in abandoned_units]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolvePendingRetreatsEvent}


class PlaceCommandTokenFromReinforcementsEvent(Event):
    def __init__(self, system_id: int) -> None:
        self.system_id = system_id

    def apply(self, previous_state: GameState) -> GameState:
        retreating_player = previous_state.turn_context.get_space_combat_context().declared_retreat
        if retreating_player is None:
            raise ValueError
        return previous_state.withdraw_command_token(
            player=retreating_player,
            from_pool=CommandTokenPool.REINFORCEMENTS,
        ).place_command_token_in_system(player=retreating_player, system_id=self.system_id)

    def __repr__(self) -> str:
        return f"PlaceCommandTokenFromReinforcementsEvent:{self.system_id}"


class PlaceCommandTokenInDestinationSystemIfAbleEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        return [
            PlaceCommandTokenFromReinforcementsEvent(
                system_id=state.turn_context.get_retreat_system_id(),
            ),
        ]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolvePendingRetreatsEvent}


def get_command_rules() -> list[CommandRule[AssignHitCommand] | CommandRule[RetreatShipCommand]]:
    return [
        EndSpaceCombatCommandRule(),
        AssignHitCommandRule(),
        UseAntiFighterBarrageCommandRule(),
        PassAntiFighterBarrageCommandRule(),
        PassStartOfCombatWindowCommandRule(),
        AnnounceRetreatCommandRule(),
        MakeCombatRollsCommandRule(),
        PassBeforeAssignHitsCommandRule(),
        SustainDamageCommandRule(),
        RetreatShipCommandRule(),
        EndRetreatCommandRule(),
    ]


def get_event_rules() -> list[EventRule]:
    return [
        OpenStartOfSpaceCombatWindowEventRule(),
        SkipSpaceCombatIfOnlyOnePlayerHasShips(),
        EndSpaceCombatEventRule(),
        CloseStartOfSpaceCombatRoundWindowsEventRule(),
        CloseAntiFighterBarrageWindowEventRule(),
        AdvanceToRollDiceStepEventRule(),
        AdvanceToAssignHitsStepEventRule(),
        DestroyUnitWhenAssignedHitEventRule(),
        AdvanceToRetreatStepEventRule(),
        OpenBeforeAssignHitsWindowEventRule(),
        SwitchAssigneeWhenFinishedAssigningEventRule(),
        RemoveAbandonedFightersAndGroundForcesEventRule(),
        PlaceCommandTokenInDestinationSystemIfAbleEventRule(),
    ]
