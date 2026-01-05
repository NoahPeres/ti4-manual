from dataclasses import dataclass, field

from src.engine.strategy_cards import StrategyCard
from src.engine.tokens import TokenType


@dataclass(frozen=True)
class TurnContext:
    has_taken_action: bool


@dataclass(frozen=True)
class Player:
    name: str
    strategy_cards: tuple[StrategyCard, ...] = field(default_factory=tuple)
    play_area: frozenset[TokenType] = field(default_factory=frozenset)
    has_passed: bool = False

    @property
    def initiative(self) -> int:
        if TokenType.NAALU_ZERO in self.play_area:
            return 0
        return min(sc.initiative for sc in self.strategy_cards) if self.strategy_cards else -1

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Player):
            raise TypeError(f"Cannot compare Player to {type(other).__name__}")
        return self.name == other.name


@dataclass(frozen=True)
class GameState:
    players: tuple[Player, ...]
    active_player: Player
    turn_context: TurnContext = field(default_factory=lambda: TurnContext(has_taken_action=False))

    @property
    def initiative_order(self) -> tuple[Player, ...]:
        return tuple(
            sorted(
                (player for player in self.players if not player.has_passed),
                key=lambda p: p.initiative,
            )
        )

    @property
    def has_taken_turn(self) -> bool:
        return self.turn_context.has_taken_action or self.active_player.has_passed
