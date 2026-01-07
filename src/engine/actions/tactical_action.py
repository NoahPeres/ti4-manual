from collections.abc import Sequence
from dataclasses import dataclass, replace

from src.engine.core.command import Command, CommandRule, CommandRuleWhenApplicable, CommandType
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState


@dataclass(frozen=True)
class ActivateCommand(Command):
    system_id: int


class TacticalActionCompletedEvent(Event):
    payload: str = "TacticalActionCompletedEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return replace(
            previous_state, turn_context=replace(previous_state.turn_context, has_taken_action=True)
        )


class InitiateTacticalActionCommandRule(CommandRuleWhenApplicable):
    def __repr__(self) -> str:
        return "InitiateTacticalAction"

    @staticmethod
    def is_applicable(command: Command) -> bool:
        return command.command_type == CommandType.INITIATE_TACTICAL_ACTION

    def is_legal_given_applicable(self, state: GameState, command: Command) -> bool:
        if not isinstance(command, ActivateCommand):
            raise TypeError(f"Expected ActivateCommand, got {type(command).__name__}")
        try:
            system = state.get_system(id=command.system_id)
        except ValueError:
            return False
        return (
            (state.active_player == command.actor)
            and not state.has_taken_turn
            and not any(token.player_name == command.actor.name for token in system.command_tokens)
        )

    def derive_events_given_applicable(self, state: GameState, command: Command) -> Sequence[Event]:
        return [TacticalActionCompletedEvent()]


def get_command_rules() -> list[CommandRule]:
    return [InitiateTacticalActionCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
