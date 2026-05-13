import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.event import Event
    from src.engine.core.game_state import GameState
    from src.engine.core.player import Player


class CommandType(enum.StrEnum):
    END_TURN = "end_turn"
    ALWAYS_VALID = "always_valid"
    ALWAYS_INVALID = "always_invalid"
    INITIATE_TACTICAL_ACTION = "initiate_tactical_action"
    PASS_ACTION = "pass_action"
    END_MOVEMENT = "end_movement"
    MOVE_SHIP = "move_ship"
    USE_SPACE_CANNON = "use_space_cannon"

    @staticmethod
    def all_command_types() -> list[CommandType]:
        return list(CommandType.__members__.values())


@dataclass(frozen=True)
class Command:
    actor: Player
    command_type: CommandType


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    info: str = ""


class CommandRule[C: Command](Protocol):
    def __repr__(self) -> str: ...
    @staticmethod
    def handles_command_types() -> set[CommandType]: ...
    def validate_legality(self, state: GameState, command: C) -> ValidationResult: ...
    def derive_events(self, state: GameState, command: C) -> Sequence[Event]: ...
