from dataclasses import dataclass, field
from enum import StrEnum


class ShipKind(StrEnum):
    FLAGSHIP = "flagship"
    DREADNOUGHT = "dreadnought"
    CRUISER = "cruiser"
    DESTROYER = "destroyer"
    FIGHTER = "fighter"


@dataclass(frozen=True)
class ShipStats:
    cost: int | None = None
    combat: int | None = None
    move: int | None = None
    capacity: int | None = None


@dataclass(frozen=True)
class Ship:
    ship_id: int
    owner_name: str
    kind: ShipKind
    stats: ShipStats = field(default_factory=ShipStats)
