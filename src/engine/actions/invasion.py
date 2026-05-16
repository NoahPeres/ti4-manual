from typing import TYPE_CHECKING

from src.engine.actions.tactical_action import (
    AdvanceToInvasionStepEvent,
    InvalidActiveSystemError,
)
from src.engine.core.command import Command, CommandRule, CommandType, ValidationResult
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import Ability, GameState, Window
from src.engine.core.windows import CloseWindowEvent, OpenWindowEvent

if TYPE_CHECKING:
    from collections.abc import Sequence


class OpenBombardmentWindowEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {AdvanceToInvasionStepEvent}

    def on_event(self, state: GameState, event: Event) -> list[Event]:
        del event
        if state.active_system is None:
            raise InvalidActiveSystemError
        return [OpenWindowEvent(window=Window.TACTICAL_ACTION_BOMBARDMENT)]


class ResolveBombardmentEvent(Event):
    def __repr__(self) -> str:
        return "ResolveBombardmentEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.use_ability_for_player(
            player=previous_state.active_player,
            ability=Ability.BOMBARDMENT,
        )  # TODO: Implement actual bombardment resolution logic.


class ResolveBombardmentCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "ResolveBombardmentCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_BOMBARDMENT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.TACTICAL_ACTION_BOMBARDMENT):
            return ValidationResult(
                is_valid=False,
                info="Cannot use bombardment outside of bombardment window.",
            )
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only active player can use bombardment.")
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> list[Event]:
        del state, command
        return [ResolveBombardmentEvent()]


class PassBombardmentCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassBombardmentCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_BOMBARDMENT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.TACTICAL_ACTION_BOMBARDMENT):
            return ValidationResult(
                is_valid=False,
                info="Cannot pass bombardment outside of bombardment window.",
            )
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only active player can pass bombardment.")
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> list[Event]:
        del state, command
        return [PassBombardmentEvent()]


class PassBombardmentEvent(Event):
    def __repr__(self) -> str:
        return "PassBombardmentEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.pass_on_window_for_player(
            player=previous_state.active_player,
            window=Window.TACTICAL_ACTION_BOMBARDMENT,
        )


class CloseBombardmentWindowEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolveBombardmentEvent, PassBombardmentEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if state.active_system is None:
            raise InvalidActiveSystemError
        if not state.player_may_resolve_bombardment_in_system(
            player=state.active_player,
            system_id=state.active_system.id,
        ):
            return [CloseWindowEvent(window=Window.TACTICAL_ACTION_BOMBARDMENT)]
        return []


def get_command_rules() -> list[CommandRule[Command]]:
    return [ResolveBombardmentCommandRule(), PassBombardmentCommandRule()]


def get_event_rules() -> list[EventRule]:
    return [OpenBombardmentWindowEventRule(), CloseBombardmentWindowEventRule()]
