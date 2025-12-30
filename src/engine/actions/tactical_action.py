from collections.abc import Sequence

from src.engine.core.command import Command, CommandRule, CommandRuleWhenApplicable, CommandType
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, TurnContext


class TacticalActionCompletedEvent(Event):
    payload: str = "TacticalActionCompletedEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return GameState(
            players=previous_state.players,
            active_player=previous_state.active_player,
            turn_context=TurnContext(has_taken_action=True),
        )


class InitiateTacticalActionCommandRule(CommandRuleWhenApplicable):
    def __repr__(self) -> str:
        return "InitiateTacticalAction"

    @staticmethod
    def is_applicable(command: Command) -> bool:
        return command.command_type == CommandType.INITIATE_TACTICAL_ACTION

    def is_legal_given_applicable(self, state: GameState, command: Command) -> bool:
        return (state.active_player == command.actor) and not state.has_taken_turn

    def derive_events_given_applicable(self, state: GameState, command: Command) -> Sequence[Event]:
        return [TacticalActionCompletedEvent()]


def get_command_rules() -> list[CommandRule]:
    return [InitiateTacticalActionCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
