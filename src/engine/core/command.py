from collections.abc import Sequence
from typing import Protocol

from src.engine.core.game_state import GameState, Player
from src.engine.core.event import Event


class Command(Protocol):
    actor: Player

    def pre_validate(self, state: GameState) -> bool: ...

    def derive_events(self, state: GameState) -> Sequence[Event]: ...
