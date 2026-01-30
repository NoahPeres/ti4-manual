import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar

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

    @staticmethod
    def all_command_types() -> list[CommandType]:
        return list(CommandType.__members__.values())


@dataclass(frozen=True)
class Command:
    actor: Player
    command_type: CommandType


class CommandRule[C: Command](Protocol):
    def __repr__(self) -> str: ...
    @staticmethod
    def is_applicable(command: Command) -> bool: ...
    def validate_legality(self, state: GameState, command: C) -> bool: ...
    def derive_events(self, state: GameState, command: C) -> Sequence[Event]: ...


class CommandRuleWhenApplicable[C: Command](ABC, CommandRule[C]):
    @abstractmethod
    def __repr__(self) -> str: ...
    @staticmethod
    @abstractmethod
    def is_applicable(command: Command) -> bool: ...
    @abstractmethod
    def is_legal_given_applicable(self, state: GameState, command: C) -> bool: ...
    @abstractmethod
    def derive_events_given_applicable(self, state: GameState, command: C) -> Sequence[Event]: ...

    def validate_legality(self, state: GameState, command: C) -> bool:
        if not self.is_applicable(command):
            return True
        else:
            return self.is_legal_given_applicable(state=state, command=command)

    def derive_events(self, state: GameState, command: C) -> Sequence[Event]:
        if not self.is_applicable(command):
            return []
        else:
            return self.derive_events_given_applicable(state=state, command=command)
