from dataclasses import dataclass
from enum import StrEnum


@dataclass
class CommandToken:
    player_name: str


class TokenType(StrEnum):
    NAALU_ZERO = "NAALU_ZERO"


UNIQUE_TOKENS: set[TokenType] = {
    TokenType.NAALU_ZERO,
}
