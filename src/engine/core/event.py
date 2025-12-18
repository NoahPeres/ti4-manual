from typing import Protocol

from src.engine.core.game_state import GameState


class Event(Protocol):
    payload: str

    def apply(self, previous_state: GameState) -> GameState: ...
