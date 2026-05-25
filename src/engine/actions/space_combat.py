from typing import TYPE_CHECKING

from src.engine.actions.movement import EndMovementStepEvent, OpenWindowEvent
from src.engine.actions.tactical_action import (
    AdvanceToInvasionStepEvent,
    AdvanceToSpaceCombatStepEvent,
)
from src.engine.core.command import Command, CommandRule, CommandType, ValidationResult
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import (
    ContextNotFoundError,
    GameState,
    SpaceCombatContext,
    SpaceCombatStep,
    TacticalActionStep,
    Window,
)
from src.engine.core.windows import CloseWindowEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.player import Player

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

    def derive_events(self, state: GameState, command: Command) -> list[Event]:
        del state, command
        return [AdvanceToInvasionStepEvent()]


class DestroyUnitEvent(Event):
    def __init__(self, unit_id: int) -> None:
        self.unit_id = unit_id

    def __repr__(self) -> str:
        return f"DestroyUnitEvent(unit_id={self.unit_id})"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.resolve_assigned_hit(unit_id=self.unit_id)


class EndAssignHitsCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "EndAssignHitsCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_ASSIGN_HITS}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del command

        return [DestroyUnitEvent(unit_id) for unit_id in state.get_pending_assigned_hits()]


class EndSpaceCombatEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {DestroyUnitEvent}

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
        ) and (len(state.turn_context.get_space_combat_context().assigned_hits) == 0):
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

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state
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
            ]
        return []


class UseAntiFighterBarrageCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "UseAntiFighterBarrageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_ANTI_FIGHTER_BARRAGE}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del command
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
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state, command
        return []


class PassAntiFighterBarrageCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassAntiFighterBarrageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_ANTI_FIGHTER_BARRAGE}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state, command
        return []


def get_command_rules() -> list[CommandRule[Command]]:
    return [
        EndSpaceCombatCommandRule(),
        EndAssignHitsCommandRule(),
        UseAntiFighterBarrageCommandRule(),
        PassAntiFighterBarrageCommandRule(),
        PassStartOfCombatWindowCommandRule(),
    ]


def get_event_rules() -> list[EventRule]:
    return [
        OpenStartOfSpaceCombatWindowEventRule(),
        SkipSpaceCombatIfOnlyOnePlayerHasShips(),
        EndSpaceCombatEventRule(),
        CloseStartOfSpaceCombatRoundWindowsEventRule(),
    ]
