from dataclasses import dataclass, field
from enum import StrEnum

from src.engine.core.player import Player
from src.engine.tokens import CommandToken


@dataclass(frozen=True)
class TurnContext:
    has_taken_action: bool


class Phase(StrEnum):
    STRATEGY = "strategy"
    ACTION = "action"
    STATUS = "status"
    AGENDA = "agenda"


@dataclass(frozen=True)
class System:
    id: int
    command_tokens: tuple[CommandToken, ...]


Galaxy = set[System]


@dataclass(frozen=True)
class GameState:
    players: tuple[Player, ...]
    active_player: Player
    phase: Phase
    galaxy: Galaxy
    turn_context: TurnContext = field(default_factory=lambda: TurnContext(has_taken_action=False))

    @property
    def initiative_order(self) -> tuple[Player, ...]:
        return tuple(
            sorted(
                self.players,
                key=lambda p: p.initiative,
            )
        )

    @property
    def initiative_order_unpassed(self) -> tuple[Player, ...]:
        return tuple(player for player in self.initiative_order if not player.has_passed)

    @property
    def has_taken_turn(self) -> bool:
        return self.turn_context.has_taken_action or self.active_player.has_passed

    def get_system(self, id: int) -> System:
        try:
            return next(system for system in self.galaxy if system.id == id)
        except StopIteration:
            raise ValueError(f"System with id {id} not found in galaxy") from None
