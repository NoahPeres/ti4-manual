from dataclasses import replace

from src.engine.core.event import Event
from src.engine.core.game_state import GameState, Window


class OpenWindowEvent(Event):
    def __init__(self, window: Window) -> None:
        self.window: Window = window
        self.payload: str = f"OpenWindow{window}"

    def apply(self, previous_state: GameState) -> GameState:
        return replace(previous_state, active_windows=(*previous_state.active_windows, self.window))


def flush_ability_trackers(game_state: GameState) -> GameState:
    return replace(
        game_state,
        turn_context=replace(game_state.turn_context, player_abilities_in_window=frozenset()),
    )


class CloseWindowEvent(Event):
    def __init__(self, window: Window) -> None:
        self.window = window
        self.payload: str = f"CloseWindow{window}"

    def apply(self, previous_state: GameState) -> GameState:
        if self.window not in previous_state.active_windows:
            raise ValueError("You cannot close a window which is not open.")
        innermost_window = max(
            i for i, window in enumerate(previous_state.active_windows) if window == self.window
        )
        return replace(
            flush_ability_trackers(previous_state),
            active_windows=(
                *previous_state.active_windows[:innermost_window],
                *previous_state.active_windows[innermost_window + 1 :],
            ),
        )
