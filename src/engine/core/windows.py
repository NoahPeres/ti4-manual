from dataclasses import replace
from typing import TYPE_CHECKING

from src.engine.core.event import Event

if TYPE_CHECKING:
    from src.engine.core.game_state import GameState, Window


class OpenWindowEvent(Event):
    def __init__(self, window: Window) -> None:
        self.window: Window = window

    def __repr__(self) -> str:
        return f"OpenWindowEvent:{self.window.value}"

    def apply(self, previous_state: GameState) -> GameState:
        return replace(
            previous_state,
            window_context=replace(
                previous_state.window_context,
                active_windows=(*previous_state.window_context.active_windows, self.window),
            ),
        )


def flush_ability_trackers(game_state: GameState) -> GameState:
    return replace(
        game_state,
        window_context=replace(game_state.window_context, player_abilities_in_window=frozenset()),
    )


class CloseWindowEvent(Event):
    def __init__(self, window: Window) -> None:
        self.window = window

    def __repr__(self) -> str:
        return f"CloseWindowEvent:{self.window}"

    def apply(self, previous_state: GameState) -> GameState:
        if self.window not in previous_state.window_context.active_windows:
            raise ValueError("You cannot close a window which is not open.")
        innermost_window = max(
            i
            for i, window in enumerate(previous_state.window_context.active_windows)
            if window == self.window
        )
        new_state = flush_ability_trackers(previous_state)
        return replace(
            new_state,
            window_context=replace(
                new_state.window_context,
                active_windows=(
                    *new_state.window_context.active_windows[:innermost_window],
                    *new_state.window_context.active_windows[innermost_window + 1 :],
                ),
            ),
        )
