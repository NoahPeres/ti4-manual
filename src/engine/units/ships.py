from dataclasses import dataclass
from enum import StrEnum


class ShipKind(StrEnum):
    FLAGSHIP = "flagship"
    DREADNOUGHT = "dreadnought"
    CRUISER = "cruiser"
    DESTROYER = "destroyer"
    FIGHTER = "fighter"


@dataclass(frozen=True)
class Ship:
    id: int
    owner_name: str
    kind: ShipKind
