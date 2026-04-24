from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ShipKind(StrEnum):
    FLAGSHIP = "flagship"
    DREADNOUGHT = "dreadnought"
    CRUISER = "cruiser"
    DESTROYER = "destroyer"
    FIGHTER = "fighter"
    CARRIER = "carrier"


class GroundForceKind(StrEnum):
    INFANTRY = "infantry"
    MECH = "mech"


def kind_from_str(unit_kind_str: str) -> ShipKind | GroundForceKind:
    if unit_kind_str in ShipKind._member_names_:
        return ShipKind[unit_kind_str]
    if unit_kind_str in GroundForceKind._member_names_:
        return GroundForceKind[unit_kind_str]
    raise ValueError(f"Invalid unit kind string: {unit_kind_str}")


UnitKind = ShipKind | GroundForceKind


@dataclass(frozen=True)
class UnitStats:
    cost: int | None = None
    combat: int | None = None
    move: int | None = None
    capacity: int | None = None


class Unit(Protocol):
    unit_id: int
    owner_name: str
    stats: UnitStats
    system_id: int | None

    def is_transportable(self) -> bool: ...


@dataclass(frozen=True)
class Ship(Unit):
    unit_id: int
    owner_name: str
    stats: UnitStats
    system_id: int | None
    kind: ShipKind

    def is_transportable(self) -> bool:
        return self.kind == ShipKind.FIGHTER


@dataclass(frozen=True)
class Fighter(Ship):
    quantity: int = 1


@dataclass(frozen=True)
class GroundForce(Unit):
    unit_id: int
    owner_name: str
    stats: UnitStats
    system_id: int | None
    kind: GroundForceKind

    def is_transportable(self) -> bool:
        return True


@dataclass(frozen=True)
class Infantry(GroundForce):
    quantity: int = 1


print(kind_from_str("FIGHTER"))
