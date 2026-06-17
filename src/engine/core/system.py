from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from src.engine.core.player import Player
    from src.engine.tokens import CommandToken


@dataclass(frozen=True)
class Planet:
    planet_id: int
    controller: Player | None = None


class SystemAlreadyHasCommandTokenError(ValueError):
    pass


@dataclass(frozen=True)
class System:
    id: int
    command_tokens: tuple[CommandToken, ...]
    coordinates: HexCoord | None = None
    planets: frozenset[Planet] = field(default_factory=frozenset[Planet])

    def has_command_token(self, player: Player) -> bool:
        return any(token.player_name == player.name for token in self.command_tokens)

    def is_adjacent_to(self, system: System) -> bool:
        return calculate_move_distance(self, system) == 1

    def place_command_token(self, command_token: CommandToken) -> Self:
        if command_token in self.command_tokens:
            raise SystemAlreadyHasCommandTokenError
        return replace(self, command_tokens=tuple(list(self.command_tokens) + [command_token]))


@dataclass(frozen=True)
class HexCoord:
    x: int
    y: int


def distance(coordinates_a: HexCoord, coordinates_b: HexCoord) -> int:
    """Convention here: Mecatol Rex is (0,0), up is y+=1, up-right is x+=1 and y+=1,
    down-right is x+=1 and y-=1. That is, there are two cases:
    If the point is between y and x axes, then you can always reach it along a sequence
    of up-right moves, plus some number of down-right moves. The number of up-right moves is
    min(|dx|, |dy|), and the number of remaining moves is abs(|dx| - |dy|).
    If the point is between y and -x axes, then you can always reach it along a sequence
    of up moves plus some number of up-left moves. The number of up moves is |dy|, and the
    number of up-left moves is |dx|. Negative values of dx and dy correspond to down and
    down-right moves, respectively."""
    dx = coordinates_b.x - coordinates_a.x
    dy = coordinates_b.y - coordinates_a.y
    if dx * dy >= 0:
        return max(abs(dx), abs(dy))
    return abs(dx) + abs(dy)


class InvalidCoordinatesError(ValueError):
    def __init__(self, systems: tuple[System, ...]) -> None:
        super().__init__(f"Invalid coordinates for systems: {systems}")


def calculate_move_distance(system_a: System, system_b: System) -> int:
    if system_a.coordinates is None or system_b.coordinates is None:
        raise InvalidCoordinatesError(systems=(system_a, system_b))
    return distance(system_a.coordinates, system_b.coordinates)
