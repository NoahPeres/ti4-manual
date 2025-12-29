from enum import StrEnum


class TokenType(StrEnum):
    NAALU_ZERO = "NAALU_ZERO"


UNIQUE_TOKENS: set[TokenType] = {
    TokenType.NAALU_ZERO,
}
