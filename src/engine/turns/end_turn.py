from collections.abc import Sequence

from src.engine.core.command import Command, CommandRule, CommandRuleWhenApplicable, CommandType
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, TurnContext


class EndTurnEvent(Event):
    payload: str = "EndTurnEvent"

    def apply(self, previous_state: GameState) -> GameState:
        if previous_state.active_player not in previous_state.initiative_order:
            raise ValueError("Active player not in initiative order")
        current_index: int = previous_state.initiative_order.index(previous_state.active_player)
        next_index: int = (current_index + 1) % len(previous_state.initiative_order)
        new_active_player = previous_state.initiative_order[next_index]
        return GameState(
            players=previous_state.players,
            active_player=new_active_player,
            turn_context=TurnContext(has_taken_action=False, has_passed=False),
        )


class EndTurn(CommandRuleWhenApplicable):
    def __repr__(self) -> str:
        return "EndTurn"

    @staticmethod
    def is_applicable(command: Command) -> bool:
        return command.command_type == CommandType.END_TURN

    def is_legal_given_applicable(self, state: GameState, command: Command) -> bool:
        return (state.active_player == command.actor) and state.turn_context.has_taken_turn

    def derive_events_given_applicable(self, state: GameState, command: Command) -> Sequence[Event]:
        return [EndTurnEvent()]


def get_command_rules() -> list[CommandRule]:
    return [EndTurn()]


def get_event_rules() -> list[EventRule]:
    return []
