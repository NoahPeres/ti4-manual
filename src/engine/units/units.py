from dataclasses import dataclass, field
from enum import StrEnum


class ShipKind(StrEnum):
    FLAGSHIP = "flagship"
    DREADNOUGHT = "dreadnought"
    CRUISER = "cruiser"
    DESTROYER = "destroyer"
    FIGHTER = "fighter"


class GroundForceKind(StrEnum):
    INFANTRY = "infantry"
    MECH = "mech"


@dataclass(frozen=True)
class UnitStats:
    cost: int | None = None
    combat: int | None = None
    move: int | None = None
    capacity: int | None = None


@dataclass(frozen=True)
class Ship:
    ship_id: int
    owner_name: str
    kind: ShipKind
    stats: UnitStats = field(default_factory=UnitStats)


@dataclass(frozen=True)
class Fighter(Ship):
    quantity: int = 1


@dataclass(frozen=True)
class GroundForce:
    ground_force_id: int
    owner_name: str
    kind: GroundForceKind
    stats: UnitStats = field(default_factory=UnitStats)


@dataclass(frozen=True)
class Infantry(GroundForce):
    quantity: int = 1
