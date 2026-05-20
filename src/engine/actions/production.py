from src.engine.core.command import CommandRule, Command, CommandType, ValidationResult
from src.engine.core.game_state import GameState, TacticalActionStep
from collections.abc import Sequence
from src.engine.core.event import Event, EventRule


class TacticalActionCompletedEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state

    def __repr__(self) -> str:
        return "TacticalActionCompletedEvent"


class ResolveProductionCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "ResolveProductionCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_PRODUCTION}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.turn_context.tactical_action_step != TacticalActionStep.PRODUCTION:
            return ValidationResult(
                is_valid=False,
                info="Cannot use production outside of production window.",
            )
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only active player can use production.")
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        # TODO: Actually implement production here
        del state, command
        return [TacticalActionCompletedEvent()]


class PassProductionCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassProductionCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_PRODUCTION}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.turn_context.tactical_action_step != TacticalActionStep.PRODUCTION:
            return ValidationResult(
                is_valid=False,
                info="Cannot pass production outside of production window.",
            )
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only active player can pass production.")
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state, command
        return [TacticalActionCompletedEvent()]


def get_command_rules() -> list[CommandRule[Command]]:
    return [ResolveProductionCommandRule(), PassProductionCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
