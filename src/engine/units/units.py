from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol, runtime_checkable


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
    for enum_class in (ShipKind, GroundForceKind):
        for member in enum_class:
            if member.value == unit_kind_str:
                return member
    raise ValueError(f"Invalid unit kind string: {unit_kind_str}")


UnitKind = ShipKind | GroundForceKind


@dataclass(frozen=True)
class UnitStats:
    cost: int | None = None
    combat: int | None = None
    move: int | None = None
    capacity: int | None = None


@runtime_checkable
class Unit(Protocol):
    @property
    def unit_id(self) -> int: ...
    @property
    def owner_name(self) -> str: ...
    @property
    def stats(self) -> UnitStats: ...
    @property
    def system_id(self) -> int | None: ...
    @property
    def kind(self) -> UnitKind: ...

    @property
    def is_transportable(self) -> bool: ...

    def set_system_id(self, new_system_id: int | None) -> Unit: ...


@dataclass(frozen=True)
class Ship:
    unit_id: int
    owner_name: str
    stats: UnitStats
    system_id: int | None
    kind: ShipKind

    @property
    def is_transportable(self) -> bool:
        return self.kind == ShipKind.FIGHTER

    def set_system_id(self, new_system_id: int | None) -> Ship:
        return replace(self, system_id=new_system_id)


@dataclass(frozen=True)
class GroundForce:
    unit_id: int
    owner_name: str
    stats: UnitStats
    system_id: int | None
    kind: GroundForceKind

    @property
    def is_transportable(self) -> bool:
        return True

    def set_system_id(self, new_system_id: int | None) -> GroundForce:
        return replace(self, system_id=new_system_id)


unit_stats_lookup: dict[UnitKind, UnitStats] = {
    ShipKind.DESTROYER: UnitStats(cost=1, combat=9, move=2),
    ShipKind.FIGHTER: UnitStats(cost=1, combat=9),
    ShipKind.DREADNOUGHT: UnitStats(cost=4, combat=5, move=1, capacity=1),
    ShipKind.CARRIER: UnitStats(cost=3, combat=9, move=1, capacity=4),
    ShipKind.CRUISER: UnitStats(cost=2, combat=7, move=2),
    ShipKind.FLAGSHIP: UnitStats(cost=8, combat=7, move=1, capacity=3),
    GroundForceKind.INFANTRY: UnitStats(cost=1, combat=8),
    GroundForceKind.MECH: UnitStats(cost=2, combat=6),
}


def make_unit_with_id(
    unit_id: int,
    owner_name: str,
    kind: UnitKind,
    system_id: int | None = None,
) -> Unit:
    stats = unit_stats_lookup[kind]
    if isinstance(kind, ShipKind):
        return Ship(
            unit_id=unit_id,
            owner_name=owner_name,
            stats=stats,
            system_id=system_id,
            kind=kind,
        )
    return GroundForce(
        unit_id=unit_id,
        owner_name=owner_name,
        stats=stats,
        system_id=system_id,
        kind=kind,
    )
