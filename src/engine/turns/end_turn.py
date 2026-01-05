from collections.abc import Sequence

from src.engine.core.command import Command, CommandRule, CommandRuleWhenApplicable, CommandType
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, TurnContext, Player


class EndTurnEvent(Event):
    payload: str = "EndTurnEvent"

    def apply(self, previous_state: GameState) -> GameState:
        current_initiative = previous_state.active_player.initiative
        higher_initiatives = [
            player
            for player in previous_state.initiative_order
            if player.initiative > current_initiative
        ]
        lower_initiatives = [
            player
            for player in previous_state.initiative_order
            if player.initiative <= current_initiative
        ]
        next_player: Player
        if higher_initiatives:
            next_player = min(higher_initiatives, key=lambda x: x.initiative)
        elif lower_initiatives:
            next_player = min(lower_initiatives, key=lambda x: x.initiative)
        else:
            raise NotImplementedError("No unpassed players remaining")
        return GameState(
            players=previous_state.players,
            active_player=next_player,
            turn_context=TurnContext(has_taken_action=False),
        )


class EndTurn(CommandRuleWhenApplicable):
    def __repr__(self) -> str:
        return "EndTurn"

    @staticmethod
    def is_applicable(command: Command) -> bool:
        return command.command_type == CommandType.END_TURN

    def is_legal_given_applicable(self, state: GameState, command: Command) -> bool:
        return (state.active_player == command.actor) and state.has_taken_turn

    def derive_events_given_applicable(self, state: GameState, command: Command) -> Sequence[Event]:
        return [EndTurnEvent()]


def get_command_rules() -> list[CommandRule]:
    return [EndTurn()]


def get_event_rules() -> list[EventRule]:
    return []
