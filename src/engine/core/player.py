from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Self

from src.engine.tokens import CommandToken, TokenType

if TYPE_CHECKING:
    from src.engine.strategy_cards import StrategyCard

MAX_COMMAND_TOKENS: Final[int] = 16


class CommandTokenPool(StrEnum):
    TACTIC = "tactic"
    FLEET = "fleet"
    STRATEGY = "strategy"
    REINFORCEMENTS = "reinforcements"


class NoCommandTokenError(ValueError):
    pass


def _remove_one_token_from_pool(
    pool: tuple[CommandToken, ...], command_token: CommandToken,
) -> tuple[CommandToken, ...]:
    if len(pool) == 0:
        raise NoCommandTokenError
    return tuple(
        [token for token in pool if token == command_token][1:]
        + [token for token in pool if token != command_token],
    )


@dataclass(frozen=True)
class CommandSheet:
    tactic: tuple[CommandToken, ...] = field(default_factory=tuple)
    fleet: tuple[CommandToken, ...] = field(default_factory=tuple)
    strategy: tuple[CommandToken, ...] = field(default_factory=tuple)
    reinforcements: tuple[CommandToken, ...] = field(default_factory=tuple)

    @classmethod
    def make_from_int(
        cls,
        player_name: str,
        tactic: int,
        fleet: int,
        strategy: int,
        reinforcements: int | None = None,
    ) -> CommandSheet:
        reinforcements_count = (
            reinforcements
            if reinforcements is not None
            else MAX_COMMAND_TOKENS - tactic - fleet - strategy
        )
        return cls(
            tactic=tuple(CommandToken(player_name=player_name) for _ in range(tactic)),
            fleet=tuple(CommandToken(player_name=player_name) for _ in range(fleet)),
            strategy=tuple(CommandToken(player_name=player_name) for _ in range(strategy)),
            reinforcements=tuple(
                CommandToken(player_name=player_name) for _ in range(reinforcements_count)
            ),
        )

    def remove_token_from_pool(self, command_token: CommandToken, pool: CommandTokenPool) -> Self:
        match pool:
            case CommandTokenPool.TACTIC:
                return replace(
                    self,
                    tactic=_remove_one_token_from_pool(self.tactic, command_token),
                )
            case CommandTokenPool.FLEET:
                return replace(
                    self,
                    fleet=_remove_one_token_from_pool(self.fleet, command_token),
                )
            case CommandTokenPool.STRATEGY:
                return replace(
                    self, strategy=_remove_one_token_from_pool(self.strategy, command_token),
                )
            case CommandTokenPool.REINFORCEMENTS:
                return replace(
                    self,
                    reinforcements=_remove_one_token_from_pool(self.reinforcements, command_token),
                )


@dataclass(frozen=True)
class Player:
    name: str
    strategy_cards: tuple[StrategyCard, ...] = field(default_factory=tuple)
    play_area: frozenset[TokenType] = field(default_factory=frozenset[TokenType])
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

    def __hash__(self) -> int:
        return self.name.__hash__()
