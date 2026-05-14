from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.game_state import GameState


class Event(Protocol):
    def apply(self, previous_state: GameState) -> GameState: ...
    def __repr__(self) -> str: ...


class EventRule(Protocol):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]: ...
    @staticmethod
    def handles_event_types() -> set[type[Event]]: ...
