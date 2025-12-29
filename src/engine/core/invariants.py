from src.engine.core.game_engine import GameState, GameStateInvariant
from src.engine.tokens import UNIQUE_TOKENS, TokenType


class UniqueTokenInvariant(GameStateInvariant):
    description = (
        """A token which can exist only once in the game must be unique across all players."""
    )

    def __init__(self, tokens: set[TokenType]) -> None:
        self.tokens: set[TokenType] = tokens

    def check(self, state: GameState) -> bool:
        seen_tokens: set[TokenType] = set()
        for player in state.players:
            for token in player.play_area:
                if token not in self.tokens:
                    continue
                if token in seen_tokens:
                    return False
                seen_tokens.add(token)
        return True


def make_all_invariants() -> list[GameStateInvariant]:
    return [UniqueTokenInvariant(tokens=UNIQUE_TOKENS)]
