from dataclasses import dataclass

Player = str  # Placeholder for the Player type


@dataclass(frozen=True)
class GameState:
    players: tuple[Player, ...]
    active_player: Player
