from re import A
from dataclasses import dataclass, field
from enum import StrEnum

from src.engine.core.player import Player
from src.engine.tokens import CommandToken


class TacticalActionStep(StrEnum):
    ACTIVATION = "activation"
    MOVEMENT = "movement"
    SPACE_COMBAT = "space_combat"
    INVASION = "invasion"
    PRODUCTION = "production"


class ShipKind(StrEnum):
    FLAGSHIP = "flagship"
    DREADNOUGHT = "dreadnought"
    CRUISER = "cruiser"
    DESTROYER = "destroyer"
    FIGHTER = "fighter"


@dataclass(frozen=True)
class TurnContext:
    has_taken_action: bool
    tactical_action_step: TacticalActionStep | None = None
    active_system_id: int | None = None


class Phase(StrEnum):
    STRATEGY = "strategy"
    ACTION = "action"
    STATUS = "status"
    AGENDA = "agenda"


@dataclass(frozen=True)
class System:
    id: int
    command_tokens: tuple[CommandToken, ...]
    ships: frozenset[Ship] = frozenset()

    def has_command_token(self, player: Player) -> bool:
        return any(token.player_name == player.name for token in self.command_tokens)


Galaxy = set[System]


@dataclass(frozen=True)
class Ship:
    id: int
    owner_name: str
    kind: ShipKind


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

    @property
    def active_system(self) -> System | None:
        if self.turn_context.active_system_id is None:
            return None
        return self.get_system(id=self.turn_context.active_system_id)

    def get_system(self, id: int) -> System:
        try:
            return next(system for system in self.galaxy if system.id == id)
        except StopIteration:
            raise ValueError(f"System with id {id} not found in galaxy") from None

    def get_player(self, name: str) -> Player:
        try:
            return next(player for player in self.players if player.name == name)
        except StopIteration:
            raise ValueError(f"Player with name {name} not found in game state") from None

    def get_current_system(self, ship: Ship) -> System | None:
        try:
            return next(system for system in self.galaxy if ship in system.ships)
        except StopIteration:
            raise ValueError(f"Ship with id {ship.id} not found in any system") from None

    def get_ship_from_id(self, id: int) -> Ship:
        try:
            return next(ship for system in self.galaxy for ship in system.ships if ship.id == id)
        except StopIteration:
            raise ValueError(f"Ship with id {id} not found in any system") from None
