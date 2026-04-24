from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ShipKind(StrEnum):
    FLAGSHIP = "flagship"
    DREADNOUGHT = "dreadnought"
    CRUISER = "cruiser"
    DESTROYER = "destroyer"
    FIGHTER = "fighter"


class GroundForceKind(StrEnum):
    INFANTRY = "infantry"
    MECH = "mech"


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


@dataclass(frozen=True)
class Ship(Unit):
    unit_id: int
    owner_name: str
    stats: UnitStats
    system_id: int | None
    kind: ShipKind


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


@dataclass(frozen=True)
class Infantry(GroundForce):
    quantity: int = 1
