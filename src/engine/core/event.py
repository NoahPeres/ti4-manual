from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.game_state import GameState


class Event(Protocol):
    payload: str

    def apply(self, previous_state: GameState) -> GameState: ...


class EventRule(Protocol):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]: ...
