from dataclasses import dataclass

Player = str  # Placeholder for the Player type


@dataclass(frozen=True)
class GameState:
    players: list[Player]
    active_player: Player


def post_validate(candidate_state: GameState) -> bool:
    # Game state level invariants can be checked here
    return True
