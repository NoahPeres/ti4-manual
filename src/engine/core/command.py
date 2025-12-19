import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.event import Event
    from src.engine.core.game_state import GameState, Player


class CommandType(enum.StrEnum):
    END_TURN = "end_turn"
    ALWAYS_VALID = "always_valid"
    ALWAYS_INVALID = "always_invalid"


@dataclass(frozen=True)
class Command:
    actor: Player
    type: CommandType


class CommandRule(Protocol):
    def __repr__(self) -> str: ...
    def validate_legality(self, state: GameState, command: Command) -> bool: ...
    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]: ...
