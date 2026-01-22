from dataclasses import dataclass, field

from src.engine.strategy_cards import StrategyCard
from src.engine.tokens import CommandToken, TokenType


@dataclass(frozen=True)
class CommandSheet:
    tactic: list[CommandToken] = field(default_factory=list)
    fleet: list[CommandToken] = field(default_factory=list)
    strategy: list[CommandToken] = field(default_factory=list)

    @classmethod
    def make_from_int(
        cls, player_name: str, tactic: int, fleet: int, strategy: int
    ) -> CommandSheet:
        return cls(
            tactic=[CommandToken(player_name=player_name)] * tactic,
            fleet=[CommandToken(player_name=player_name)] * fleet,
            strategy=[CommandToken(player_name=player_name)] * strategy,
        )


@dataclass(frozen=True)
class Player:
    name: str
    strategy_cards: tuple[StrategyCard, ...] = field(default_factory=tuple)
    play_area: frozenset[TokenType] = field(default_factory=frozenset)
    command_sheet: CommandSheet = field(default_factory=CommandSheet)
    has_passed: bool = False

    @property
    def initiative(self) -> int:
        if TokenType.NAALU_ZERO in self.play_area:
            return 0
        return min(sc.initiative for sc in self.strategy_cards) if self.strategy_cards else -1

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Player):
            return NotImplemented
        return self.name == other.name
