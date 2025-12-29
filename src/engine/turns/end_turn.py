from src.engine.core.command import Command, CommandRule
from src.engine.core.event import Event
from src.engine.core.game_state import GameState, Player


class EndTurnEvent(Event):
    payload: str = "EndTurnEvent"

    def apply(self, previous_state: GameState) -> GameState:
        if previous_state.active_player not in previous_state.initiative_order:
            raise ValueError("Active player not in initiative order")
        current_index: int = previous_state.initiative_order.index(previous_state.active_player)
        next_index: int = (current_index + 1) % len(previous_state.initiative_order)
        new_active_player: Player = previous_state.initiative_order[next_index]
        return GameState(
            players=previous_state.players,
            active_player=new_active_player,
        )


class EndTurn(CommandRule):
    def __repr__(self) -> str:
        return "EndTurn"

    def validate_legality(self, state: GameState, command: Command) -> bool:
        # End turn is always legal
        return state.active_player == command.actor

    def derive_events(self, state: GameState, command: Command) -> list[Event]:
        # Create an event that changes the active player to the next player

        return [EndTurnEvent()]


def get_rules() -> list[CommandRule]:
    return [EndTurn()]
