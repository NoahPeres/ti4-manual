from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class CommandToken:
    player_name: str


class TokenType(StrEnum):
    NAALU_ZERO = "NAALU_ZERO"


UNIQUE_TOKENS: set[TokenType] = {
    TokenType.NAALU_ZERO,
}
