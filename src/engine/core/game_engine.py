from src.engine.core.command import Command
from src.engine.core.game_state import GameState
from src.engine.core.event import Event
from collections.abc import Sequence
from functools import reduce
from typing import Protocol
from dataclasses import dataclass


class GameStateInvariant(Protocol):
    def check(self, state: GameState) -> bool: ...


@dataclass(frozen=True)
class CommandResult:
    new_state: GameState
    success: bool
    events: Sequence[Event]


class GameEngine:
    def __init__(self, invariants: Sequence[GameStateInvariant] | None = None):
        self.invariants: Sequence[GameStateInvariant] = (
            invariants if invariants is not None else []
        )

    def apply_command(self, state: GameState, command: Command) -> CommandResult:
        if not command.pre_validate(state):
            return CommandResult(new_state=state, success=False, events=[])
        events: Sequence[Event] = command.derive_events(state)
        new_state: GameState = reduce(lambda s, e: e.apply(s), events, initial=state)
        if not all(invariant.check(state=new_state) for invariant in self.invariants):
            return CommandResult(new_state=state, success=False, events=[])
        return CommandResult(new_state=new_state, success=True, events=events)
