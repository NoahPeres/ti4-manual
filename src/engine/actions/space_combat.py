import itertools
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
    make_command_candidates_for_all_players,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import (
    CombatRoll,
    GameState,
    InvalidRetreatError,
    SpaceCombatContext,
    SpaceCombatParticipant,
    SpaceCombatStep,
    TacticalActionStep,
    UnitAbility,
    Window,
)
from src.engine.core.player import CommandTokenPool
from src.engine.core.windows import CloseWindowEvent
from src.engine.units.sustain_damage import SustainDamageEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.dice_roller import DiceRoller
    from src.engine.core.system import System
    from src.engine.units.units import Ship, Unit


START_OF_COMBAT_ROUND_WINDOWS: list[Window] = [
    Window.START_OF_SPACE_COMBAT,
    Window.START_OF_FIRST_ROUND_OF_SPACE_COMBAT,
    Window.START_OF_SPACE_COMBAT_ROUND,
]

END_OF_COMBAT_ROUND_WINDOWS: list[Window] = [
    Window.END_OF_SPACE_COMBAT,
    Window.END_OF_SPACE_COMBAT_ROUND,
]


class StartSpaceCombatEvent(Event):
    def __repr__(self) -> str:
        return "StartSpaceCombatEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            space_combat_context=SpaceCombatContext(
                step=SpaceCombatStep.ANTI_FIGHTER_BARRAGE,
                round_number=1,
                attacker=previous_state.active_player.name,
                defender=previous_state.get_defender_in_system(
                    system_id=previous_state.get_active_system().id,
                ).name,
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
                    player_name=combat_context.defender
                    if not has_finished_assigning_hits(state, combat_context.defender)
                    else None,
                ),
            ]
        if (
            combat_context.current_hits_assignee == combat_context.defender
            and has_finished_assigning_hits(state, combat_context.defender)
        ):
            return [SetHitsAssigneeEvent(player_name=None)]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {DestroyUnitEvent, SustainDamageEvent}


def has_finished_assigning_hits(state: GameState, player_name: str) -> bool:
    combat_context = state.turn_context.get_space_combat_context()
    return (
        combat_context.unassigned_hits_for_player(player_name) == 0
    ) or not state.get_ships_in_system(
        system_id=state.get_active_system().id,
        player_name=player_name,
    )


class AdvanceToRetreatStepEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        combat_context = state.turn_context.get_space_combat_context()
        if all(
            has_finished_assigning_hits(state=state, player_name=player_name)
            and state.get_ships_in_system(state.get_active_system().id, player_name)
            for player_name in [combat_context.attacker, combat_context.defender]
        ):
            if combat_context.declared_retreat_name is None:
                return [OpenWindowEvent(Window.END_OF_SPACE_COMBAT_ROUND)]
            return [AdvanceToRetreatStepEvent()]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {DestroyUnitEvent, AdvanceToAssignHitsStepEvent, SustainDamageEvent}


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
        if (
            len(
                {
                    ship.owner_name
                    for ship in state.get_ships_in_system(state.get_active_system().id)
                },
            )
            <= 1
        ) and all(
            [
                has_finished_assigning_hits(state, combat_context.attacker),
                has_finished_assigning_hits(state, combat_context.defender),
            ],
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
                system_id=previous_state.get_active_system().id,
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


class PassStartOfCombatWindowCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassStartOfCombatWindowCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_START_OF_COMBAT_ROUND}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.START_OF_SPACE_COMBAT_ROUND):
            return ValidationResult(
                is_valid=False,
                info="Can only pass at the start of a round of combat.",
            )
        if state.window_context.player_has_passed_on_window(
            player_name=command.actor,
            window=Window.START_OF_SPACE_COMBAT_ROUND,
        ):
            return ValidationResult(is_valid=False, info="You already passed on this window.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [PassStartOfCombatWindowEvent(player_name=command.actor)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=PassStartOfCombatWindowCommandRule,
        )


class PassEndOfCombatWindowCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassEndOfCombatWindowCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_END_OF_COMBAT_ROUND}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.END_OF_SPACE_COMBAT_ROUND):
            return ValidationResult(
                is_valid=False,
                info="Can only pass at the end of a round of combat.",
            )
        if state.window_context.player_has_passed_on_window(
            player_name=command.actor,
            window=Window.END_OF_SPACE_COMBAT_ROUND,
        ):
            return ValidationResult(is_valid=False, info="You already passed on this window.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [PassEndOfCombatWindowEvent(player_name=command.actor)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=PassEndOfCombatWindowCommandRule,
        )


class PassStartOfCombatWindowEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player = player_name

    def __repr__(self) -> str:
        return f"PassStartOfCombatWindowEvent:{self.player}"

    def apply(self, previous_state: GameState) -> GameState:
        active_state = previous_state
        for window in previous_state.window_context.active_windows:
            if window in START_OF_COMBAT_ROUND_WINDOWS:
                active_state = active_state.pass_on_window_for_player(
                    player_name=self.player,
                    window=window,
                )
        return active_state


class PassEndOfCombatWindowEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player_name = player_name

    def __repr__(self) -> str:
        return f"PassEndOfCombatWindowEvent:{self.player_name}"

    def apply(self, previous_state: GameState) -> GameState:
        active_state = previous_state
        for window in previous_state.window_context.active_windows:
            if window in END_OF_COMBAT_ROUND_WINDOWS:
                active_state = active_state.pass_on_window_for_player(
                    player_name=self.player_name,
                    window=window,
                )
        return active_state


class CloseStartOfSpaceCombatRoundWindowsEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {PassStartOfCombatWindowEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        events: list[Event] = []
        if all(
            state.window_context.player_has_passed_on_window(
                player.name,
                window=Window.START_OF_SPACE_COMBAT_ROUND,
            )
            for player in state.players
        ):
            events += [
                CloseWindowEvent(window=window)
                for window in state.window_context.active_windows
                if window in START_OF_COMBAT_ROUND_WINDOWS
            ]
            if state.turn_context.get_space_combat_context().round_number == 1:
                events += [OpenWindowEvent(window=Window.ANTI_FIGHTER_BARRAGE)]
        return events


class CloseEndOfSpaceCombatRoundWindowsEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {PassEndOfCombatWindowEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        events: list[Event] = []
        if all(
            state.window_context.player_has_passed_on_window(
                player.name,
                window=Window.END_OF_SPACE_COMBAT_ROUND,
            )
            for player in state.players
        ):
            events += [
                CloseWindowEvent(window=window)
                for window in state.window_context.active_windows
                if window in END_OF_COMBAT_ROUND_WINDOWS
            ]
            if (
                len(
                    {
                        ship.owner_name
                        for ship in state.get_ships_in_system(
                            system_id=state.get_active_system().id,
                        )
                    },
                )
                > 1
            ):
                events += [
                    ResetCombatToAnnounceRetreatStepEvent(),
                    OpenWindowEvent(Window.START_OF_SPACE_COMBAT_ROUND),
                ]
        return events


class ResolveAntiFighterBarrageEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player_name = player_name

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.use_ability_for_player(
            player_name=self.player_name,
            ability=UnitAbility.ANTI_FIGHTER_BARRAGE,
        )

    def __repr__(self) -> str:
        return f"ResolveAntiFighterBarrageEvent:{self.player_name}"


class PassAntiFighterBarrageEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player_name = player_name

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.pass_on_window_for_player(
            player_name=self.player_name,
            window=Window.ANTI_FIGHTER_BARRAGE,
        )

    def __repr__(self) -> str:
        return f"PassAntiFighterBarrageEvent:{self.player_name}"


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
            player_name=command.actor,
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
        return [ResolveAntiFighterBarrageEvent(player_name=command.actor)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if state.turn_context.space_combat_context is None:
            return []
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=UseAntiFighterBarrageCommandRule,
        )


class PassAntiFighterBarrageCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassAntiFighterBarrageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_ANTI_FIGHTER_BARRAGE}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.ANTI_FIGHTER_BARRAGE):
            return ValidationResult(
                is_valid=False,
                info="Can only pass during Anti-fighter barrage step.",
            )
        if state.window_context.player_has_passed_on_window(
            player_name=command.actor,
            window=Window.ANTI_FIGHTER_BARRAGE,
        ):
            return ValidationResult(is_valid=False, info="You already passed on this window.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [PassAntiFighterBarrageEvent(player_name=command.actor)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if state.turn_context.space_combat_context is None:
            return []
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=PassAntiFighterBarrageCommandRule,
        )


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
                player_name=player_name,
                system_id=state.get_active_system().id,
            )
            for player_name in [
                state.turn_context.get_space_combat_context().attacker,
                state.turn_context.get_space_combat_context().defender,
            ]
        ):
            return [CloseWindowEvent(Window.ANTI_FIGHTER_BARRAGE), EndAntiFighterBarrageStepEvent()]
        return []


class AnnounceRetreatEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player = player_name

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().announce_retreat(
                player_name=self.player,
                is_retreating=True,
            ),
        )

    def __repr__(self) -> str:
        return "AnnounceRetreatEvent"


class PassAnnounceRetreatEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player_name = player_name

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().announce_retreat(
                player_name=self.player_name,
                is_retreating=False,
            ),
        )

    def __repr__(self) -> str:
        return "PassAnnounceRetreatEvent"


def _is_eligible_retreat_system_for_player(
    system: System,
    state: GameState,
    player_name: str,
) -> bool:
    if not state.get_active_system().is_adjacent_to(system):
        return False
    if any(
        ship.owner_name != player_name for ship in state.get_ships_in_system(system_id=system.id)
    ):
        return False
    return any(
        unit.owner_name == player_name for unit in state.get_units_in_system(system.id)
    ) or any(planet.controller == player_name for planet in system.planets)


def _check_for_eligible_retreat_system(state: GameState, player_name: str) -> ValidationResult:
    systems = state.galaxy.get_adjacent_systems(system_id=state.get_active_system().id)
    for system in systems:
        if _is_eligible_retreat_system_for_player(system, state=state, player_name=player_name):
            return ValidationResult(is_valid=True)
    return ValidationResult(is_valid=False, info="No legal retreat system found.")


def _check_declaration_ordering(
    state: GameState,
    command: Command,
    space_combat_context: SpaceCombatContext,
) -> ValidationResult:
    participant = state.turn_context.get_space_combat_context().get_participant_by_player(
        player_name=command.actor,
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


EventFactoryByPlayer = Callable[[str], Event]


class AnnounceRetreatCommandRule(CommandRule[Command]):
    _COMMAND_TO_EVENT_FACTORY: Final[dict[CommandType, EventFactoryByPlayer]] = {
        CommandType.ANNOUNCE_RETREAT: AnnounceRetreatEvent,
        CommandType.PASS_ANNOUNCE_RETREAT: PassAnnounceRetreatEvent,
    }

    @classmethod
    def _make_event_from_command(cls, command_type: CommandType, player_name: str) -> Event:
        return cls._COMMAND_TO_EVENT_FACTORY[command_type](player_name)

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

        return _check_for_eligible_retreat_system(state=state, player_name=command.actor)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [
            self._make_event_from_command(
                command_type=command.command_type,
                player_name=command.actor,
            ),
        ]

    @staticmethod
    def _candidate_commands_for_state(state: GameState) -> list[Command]:
        return [
            Command(actor=player.name, command_type=command_type)
            for command_type, player in itertools.product(
                AnnounceRetreatCommandRule.handles_command_types(),
                state.players,
            )
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if state.turn_context.space_combat_context is None:
            return []
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=AnnounceRetreatCommandRule,
        )


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
            combat_context.declared_retreat_name is not None
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
            if unit.stats.combat is not None and unit.is_ship and unit.owner_name == command.actor
        ]

    @staticmethod
    def _candidate_commands_for_state(state: GameState) -> list[Command]:
        return [
            Command(actor=player.name, command_type=command_type)
            for command_type, player in itertools.product(
                MakeCombatRollsCommandRule.handles_command_types(),
                state.players,
            )
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
    def __init__(self, player_name: str | None) -> None:
        self.player_name = player_name

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().set_hits_assignee(
                self.player_name,
            ),
        )

    def __repr__(self) -> str:
        return f"SetHitsAssigneeEvent:{self.player_name}"


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
                    player_name=combat_context.attacker,
                )
            }
            - attacker_rolled_unit_ids
        ) and not (
            {
                ship.unit_id
                for ship in state.get_ships_in_system(
                    state.get_active_system().id,
                    player_name=combat_context.defender,
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
                player_name=self.player_name,
            ),
        )


def _legal_hit_assignment(state: GameState, command: AssignHitCommand) -> ValidationResult:
    unit = state.get_unit_from_id(unit_id=command.unit_id)
    if unit.system_id != state.get_active_system().id:
        return ValidationResult(
            is_valid=False,
            info=f"Ship {unit.unit_id} is not in the active system.",
        )
    if not unit.is_ship:
        return ValidationResult(
            is_valid=False,
            info=f"Unit {unit.unit_id} is not a ship, cannot be assigned hits in space combat.",
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
        if has_finished_assigning_hits(state=state, player_name=command.actor):
            return ValidationResult(is_valid=False, info="No more hits to assign.")
        if command.actor == space_combat_context.defender and not has_finished_assigning_hits(
            state=state,
            player_name=space_combat_context.attacker,
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
    def _candidate_commands_for_state(state: GameState) -> list[AssignHitCommand]:
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

    @staticmethod
    def candidate_commands(state: GameState) -> list[AssignHitCommand]:
        if state.turn_context.space_combat_context is None:
            return []
        return AssignHitCommandRule._candidate_commands_for_state(state=state)


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
        if command.actor != state.turn_context.get_space_combat_context().current_hits_assignee:
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
        if state.turn_context.space_combat_context is None:
            return []
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=PassBeforeAssignHitsCommandRule,
        )


@dataclass(frozen=True)
class RetreatShipCommand(Command):
    ship_id: int
    to_system_id: int
    transported_unit_ids: frozenset[int] = frozenset()


def _ship_is_valid_for_retreat(
    ship: Ship,
    command: RetreatShipCommand,
    state: GameState,
) -> ValidationResult:
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
    if ship.unit_id in {move.unit_id for move in state.turn_context.pending_moves}:
        return ValidationResult(
            is_valid=False,
            info=f"This ship {ship.unit_id} already declared retreat.",
        )
    return ValidationResult(is_valid=True)


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
        if context.declared_retreat_name != command.actor:
            return ValidationResult(
                is_valid=False,
                info="Only the player who declared may retreat.",
            )
        if not _is_eligible_retreat_system_for_player(
            system=state.galaxy.get_system(command.to_system_id),
            state=state,
            player_name=command.actor,
        ):
            return ValidationResult(
                is_valid=False,
                info="System is not eligible for retreat: must contain one or more of that player's"
                " units, a planet they control, or both, as well as no ships controlled by another "
                "player.",
            )
        ship = state.get_ship_from_id(ship_id=command.ship_id)
        return _ship_is_valid_for_retreat(ship=ship, command=command, state=state)

    def derive_events(
        self,
        state: GameState,
        command: RetreatShipCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [
            AddMoveToPendingEvent(
                unit_id=command.ship_id,
                to_system_id=command.to_system_id,
            ),
        ]

    @staticmethod
    def _candidate_commands_for_state(state: GameState) -> list[RetreatShipCommand]:
        retreating_player_name = state.turn_context.get_space_combat_context().declared_retreat_name
        if retreating_player_name is None:
            return []

        eligible_systems = {
            system
            for system in state.galaxy
            if _is_eligible_retreat_system_for_player(
                system=system,
                state=state,
                player_name=retreating_player_name,
            )
        }
        return [
            RetreatShipCommand(
                actor=retreating_player_name,
                command_type=CommandType.RETREAT_SHIP,
                ship_id=ship.unit_id,
                to_system_id=system.id,
            )
            for ship in state.get_ships_in_system(state.get_active_system().id)
            if ship.owner_name == retreating_player_name
            for system in eligible_systems
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[RetreatShipCommand]:
        if state.turn_context.space_combat_context is None:
            return []
        return RetreatShipCommandRule._candidate_commands_for_state(state=state)


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
        return "EndRetreat"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_RETREAT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.turn_context.get_space_combat_context().step != SpaceCombatStep.RETREAT:
            return ValidationResult(
                is_valid=False,
                info="Can only retreat during the retreat step.",
            )
        if state.turn_context.get_space_combat_context().declared_retreat_name != command.actor:
            return ValidationResult(
                is_valid=False,
                info="Only the retreating player may resolve retreats.",
            )
        ships_in_active_system_with_move_value = {
            ship.unit_id
            for ship in state.get_ships_in_system(
                system_id=state.get_active_system().id,
                player_name=command.actor,
            )
            if ship.stats.move is not None
        }
        pending_retreats = {move.unit_id for move in state.turn_context.pending_moves}
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

    @staticmethod
    def _candidate_commands_for_state(state: GameState) -> list[Command]:
        retreating_player_name = state.turn_context.get_space_combat_context().declared_retreat_name
        if retreating_player_name is None:
            return []
        return [
            Command(
                actor=retreating_player_name,
                command_type=CommandType.END_RETREAT,
            ),
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if state.turn_context.space_combat_context is None:
            return []
        return EndRetreatCommandRule._candidate_commands_for_state(state=state)


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
            player_name=state.turn_context.get_space_combat_context().declared_retreat_name,
        )
        return [RemoveUnitEvent(unit_id=unit.unit_id) for unit in abandoned_units]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolvePendingRetreatsEvent}


class PlaceCommandTokenFromPoolEvent(Event):
    def __init__(self, system_id: int, pool: CommandTokenPool) -> None:
        self.system_id = system_id
        self.pool = pool

    def apply(self, previous_state: GameState) -> GameState:
        retreating_player_name = (
            previous_state.turn_context.get_space_combat_context().declared_retreat_name
        )
        if retreating_player_name is None:
            raise ValueError
        return previous_state.withdraw_command_token(
            player_name=retreating_player_name,
            from_pool=self.pool,
        ).place_command_token_in_system(
            player_name=retreating_player_name,
            system_id=self.system_id,
        )

    def __repr__(self) -> str:
        return f"PlaceCommandTokenFromPoolEvent:{self.system_id}:{self.pool}"


class PlaceCommandTokenInDestinationSystemIfAbleEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        retreating_player_name = state.turn_context.get_space_combat_context().declared_retreat_name
        if retreating_player_name is None:
            raise InvalidRetreatError
        command_sheet = state.get_player(retreating_player_name).command_sheet
        if len(command_sheet.reinforcements) < 1:
            return [OpenWindowEvent(Window.MUST_CHOOSE_POOL_FOR_REMOVE_COMMAND_TOKEN)]
        return [
            PlaceCommandTokenFromPoolEvent(
                system_id=state.turn_context.get_retreat_system_id(),
                pool=CommandTokenPool.REINFORCEMENTS,
            ),
        ]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolvePendingRetreatsEvent}


@dataclass(frozen=True)
class RemoveCommandTokenFromPoolCommand(Command):
    pool: CommandTokenPool


class ChoosePoolToRemoveCommandTokenCommandRule(CommandRule[RemoveCommandTokenFromPoolCommand]):
    def __repr__(self) -> str:
        return "ChoosePoolToRemoveCommandTokenCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.REMOVE_COMMAND_TOKEN_FROM_POOL}

    def validate_legality(
        self,
        state: GameState,
        command: RemoveCommandTokenFromPoolCommand,
    ) -> ValidationResult:
        if not state.window_context.is_window_active(
            Window.MUST_CHOOSE_POOL_FOR_REMOVE_COMMAND_TOKEN,
        ):
            return ValidationResult(
                is_valid=False,
                info="Can only remove token from pool in proper window.",
            )
        retreating_player_name = state.turn_context.get_space_combat_context().declared_retreat_name
        if retreating_player_name is None:
            raise InvalidRetreatError
        if retreating_player_name != command.actor:
            return ValidationResult(
                is_valid=False,
                info="Only the relevant player may choose a pool.",
            )
        if (
            len(state.get_player(retreating_player_name).command_sheet.get_pool(pool=command.pool))
            < 1
        ):
            return ValidationResult(
                is_valid=False,
                info=f"You have no tokens in {command.pool.value}.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: RemoveCommandTokenFromPoolCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del engine_context
        return [
            CloseWindowEvent(window=Window.MUST_CHOOSE_POOL_FOR_REMOVE_COMMAND_TOKEN),
            PlaceCommandTokenFromPoolEvent(
                system_id=state.turn_context.get_retreat_system_id(),
                pool=command.pool,
            ),
        ]

    @staticmethod
    def _candidate_commands_for_state(state: GameState) -> list[RemoveCommandTokenFromPoolCommand]:
        return [
            RemoveCommandTokenFromPoolCommand(
                actor=player.name,
                command_type=CommandType.REMOVE_COMMAND_TOKEN_FROM_POOL,
                pool=pool,
            )
            for player in state.players
            for pool in CommandTokenPool
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[RemoveCommandTokenFromPoolCommand]:
        if state.turn_context.space_combat_context is None:
            return []
        return ChoosePoolToRemoveCommandTokenCommandRule._candidate_commands_for_state(state=state)


class ResetCombatToAnnounceRetreatStepEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().reset_combat_round(),
        )

    def __repr__(self) -> str:
        return "ResetCombatToAnnounceRetreatStepEvent"


@dataclass(frozen=True)
class RemoveUnitCommand(Command):
    unit_id: int


class RemoveUnitDueToCapacityCommandRule(CommandRule[RemoveUnitCommand]):
    def __repr__(self) -> str:
        return "RemoveUnit"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.REMOVE_UNIT}

    def validate_legality(self, state: GameState, command: RemoveUnitCommand) -> ValidationResult:
        if not state.window_context.is_window_active(Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY):
            return ValidationResult(is_valid=False, info="No reason to remove units.")
        unit = state.get_unit_from_id(command.unit_id)
        if unit.owner_name != command.actor:
            return ValidationResult(is_valid=False, info="You cannot remove another player's unit.")
        if not unit.is_transportable:
            return ValidationResult(
                is_valid=False,
                info="Unit is not transportable: removal won't alleviate capacity.",
            )
        if unit.system_id is None:
            return ValidationResult(is_valid=False, info="Unit is not in any system.")
        if not capacity_exceeded_in_system(state=state, system_id=unit.system_id):
            return ValidationResult(is_valid=False, info="Unit is not exceeding capacity.")

        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: RemoveUnitCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [RemoveUnitEvent(unit_id=command.unit_id)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[RemoveUnitCommand]:
        if not state.window_context.is_window_active(Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY):
            return []
        units = {
            unit for unit in state.units if unit.is_transportable and unit.system_id is not None
        }
        return [
            RemoveUnitCommand(
                actor=unit.owner_name,
                command_type=CommandType.REMOVE_UNIT,
                unit_id=unit.unit_id,
            )
            for unit in units
            if unit.is_transportable
        ]


def capacity_exceeded_in_system(state: GameState, system_id: int) -> bool:
    units_in_space = state.get_units_in_space_area_of_system(system_id=system_id)
    if len({unit.owner_name for unit in units_in_space}) > 1:
        raise ValueError
    total_capacity = sum(
        [unit.stats.capacity for unit in units_in_space if unit.stats.capacity is not None],
    )
    total_capacity_required = sum([1 for unit in units_in_space if unit.is_transportable])
    return total_capacity_required > total_capacity


class CheckCapacityAfterCombatEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        if not isinstance(event, CloseWindowEvent):
            return []
        if event.window != Window.END_OF_SPACE_COMBAT:
            return []

        if not capacity_exceeded_in_system(state=state, system_id=state.get_active_system().id):
            return []
        return [OpenWindowEvent(Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY)]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {CloseWindowEvent}


class ClearCombatStateEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(None)

    def __repr__(self) -> str:
        return "ClearCombatStateEvent"


class ClearCombatStateAfterCombatEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del state
        if not isinstance(event, CloseWindowEvent):
            return []
        if event.window != Window.END_OF_SPACE_COMBAT:
            return []

        return [ClearCombatStateEvent()]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {CloseWindowEvent}


class RecheckCapacityAfterRemovalEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if not state.window_context.is_window_active(Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY):
            return []

        if capacity_exceeded_in_system(state=state, system_id=state.get_active_system().id):
            return []
        return [CloseWindowEvent(Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY)]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {RemoveUnitEvent}


class CloseBeforeAssignHitsWindowIfAllHitsCancelledEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        context = state.turn_context.get_space_combat_context()
        if context.current_hits_assignee is not None and has_finished_assigning_hits(
            state=state,
            player_name=context.current_hits_assignee,
        ):
            return [CloseWindowEvent(Window.BEFORE_ASSIGNING_HITS)]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {SustainDamageEvent}


def get_command_rules() -> list[
    CommandRule[AssignHitCommand]
    | CommandRule[RetreatShipCommand]
    | CommandRule[RemoveCommandTokenFromPoolCommand]
    | CommandRule[RemoveUnitCommand]
    | CommandRule[Command]
]:
    return [
        AssignHitCommandRule(),
        UseAntiFighterBarrageCommandRule(),
        PassAntiFighterBarrageCommandRule(),
        PassStartOfCombatWindowCommandRule(),
        AnnounceRetreatCommandRule(),
        MakeCombatRollsCommandRule(),
        PassBeforeAssignHitsCommandRule(),
        RetreatShipCommandRule(),
        EndRetreatCommandRule(),
        ChoosePoolToRemoveCommandTokenCommandRule(),
        PassEndOfCombatWindowCommandRule(),
        RemoveUnitDueToCapacityCommandRule(),
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
        CloseEndOfSpaceCombatRoundWindowsEventRule(),
        CheckCapacityAfterCombatEventRule(),
        RecheckCapacityAfterRemovalEventRule(),
        ClearCombatStateAfterCombatEventRule(),
        CloseBeforeAssignHitsWindowIfAllHitsCancelledEventRule(),
    ]
