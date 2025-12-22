from src.engine.core.event import Event
from src.engine.core.game_engine import GameStateInvariant
from src.engine.core.game_state import GameState


class FailingInvariant(GameStateInvariant):
    description: str = "Always fails invariant"

    def check(self, state: GameState) -> bool:
        return False  # Always fails


class TrivialEvent(Event):
    def __init__(self, payload: str) -> None:
        self.payload: str = payload

    def apply(self, previous_state):
        # For testing purposes, we just return the previous state unchanged
        return previous_state
