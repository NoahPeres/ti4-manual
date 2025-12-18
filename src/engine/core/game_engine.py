from src.engine.core.command import Command
from src.engine.core.game_state import GameState
from src.engine.core.event import Event
from collections.abc import Sequence
from functools import reduce
from typing import Protocol


class GameStateInvariant(Protocol):
    def check(self, state: GameState) -> bool: ...


class GameEngine:
    def __init__(self, invariants: Sequence[GameStateInvariant] = []):
        self.invariants: Sequence[GameStateInvariant] = invariants

    def apply_command(self, state: GameState, command: Command) -> GameState:
        if not command.pre_validate(state):
            return state
        events: Sequence[Event] = command.derive_events(state)
        new_state: GameState = reduce(lambda s, e: e.apply(s), events, initial=state)
        if not all(invariant.check(state=new_state) for invariant in self.invariants):
            return state
        return new_state
