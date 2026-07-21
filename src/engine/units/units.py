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
    WAR_SUN = "war_sun"


class GroundForceKind(StrEnum):
    INFANTRY = "infantry"
    MECH = "mech"


class UnitAbility(StrEnum):
    SPACE_CANNON = "space_cannon"
    BOMBARDMENT = "bombardment"
    ANTI_FIGHTER_BARRAGE = "anti_fighter_barrage"
    SUSTAIN_DAMAGE = "sustain_damage"


class InvalidUnitKindError(ValueError):
    def __init__(self, kind: str) -> None:
        super().__init__(f"Invalid unit kind: {kind}")


def kind_from_str(unit_kind_str: str) -> ShipKind | GroundForceKind:
    for enum_class in (ShipKind, GroundForceKind):
        for member in enum_class:
            if member.value == unit_kind_str:
                return member
    raise InvalidUnitKindError(unit_kind_str)


UnitKind = ShipKind | GroundForceKind


class InvalidUnitStatsError(ValueError):
    def __init__(self, attribute: str, value: int | None) -> None:
        super().__init__(f"Invalid unit stats: {attribute} = {value}")


@dataclass(frozen=True)
class UnitStats:
    cost: int | None = None
    combat: int | None = None
    move: int | None = None
    capacity: int | None = None
    burst_icons: int | None = None
    unit_abilities: frozenset[UnitAbility] = frozenset()

    def __post_init__(self) -> None:
        if self.burst_icons is not None and self.burst_icons <= 0:
            raise InvalidUnitStatsError("burst_icons", self.burst_icons)

    @property
    def num_dice(self) -> int:
        return 1 if self.burst_icons is None else self.burst_icons


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
    @property
    def is_ship(self) -> bool: ...
    @property
    def is_ground_force(self) -> bool: ...
    @property
    def is_in_reinforcements(self) -> bool: ...
    @property
    def is_in_space_area(self) -> bool: ...
    @property
    def is_damaged(self) -> bool: ...

    def set_system_id(self, new_system_id: int | None) -> Unit: ...

    def cast_to_ship(self) -> Ship: ...

    def cast_to_ground_force(self) -> GroundForce: ...

    def set_is_damaged(self, *, is_damaged: bool) -> Unit: ...


class NotAShipError(TypeError):
    def __init__(self, data: str = "Unit") -> None:
        super().__init__(f"{data} is not a ship and cannot be cast to a ship")


class NotAGroundForceError(TypeError):
    def __init__(self, data: str = "Unit") -> None:
        super().__init__(f"{data} is not a ground force and cannot be cast to a ground force")


@dataclass(frozen=True)
class Ship:
    unit_id: int
    owner_name: str
    stats: UnitStats
    system_id: int | None
    kind: ShipKind
    is_damaged: bool = False

    @property
    def is_transportable(self) -> bool:
        return self.kind == ShipKind.FIGHTER

    @property
    def is_ship(self) -> bool:
        return True

    @property
    def is_ground_force(self) -> bool:
        return False

    @property
    def is_in_reinforcements(self) -> bool:
        return self.system_id is None

    @property
    def is_in_space_area(self) -> bool:
        return True

    def set_system_id(self, new_system_id: int | None) -> Ship:
        return replace(self, system_id=new_system_id)

    def cast_to_ship(self) -> Ship:
        return self

    def cast_to_ground_force(self) -> GroundForce:
        if not self.is_ground_force:
            raise NotAGroundForceError(self.__repr__())
        raise NotImplementedError

    def set_is_damaged(self, *, is_damaged: bool) -> Ship:
        return replace(self, is_damaged=is_damaged)


@dataclass(frozen=True)
class GroundForce:
    unit_id: int
    owner_name: str
    stats: UnitStats
    system_id: int | None
    kind: GroundForceKind
    planet_id: int | None = None
    is_damaged: bool = False

    @property
    def is_transportable(self) -> bool:
        return True

    @property
    def is_ship(self) -> bool:
        return False

    @property
    def is_ground_force(self) -> bool:
        return True

    @property
    def is_in_reinforcements(self) -> bool:
        return self.system_id is None

    @property
    def is_in_space_area(self) -> bool:
        return self.system_id is not None and self.planet_id is None

    def set_system_id(self, new_system_id: int | None) -> GroundForce:
        return replace(self, system_id=new_system_id)

    def set_planet_id(self, new_planet_id: int | None) -> GroundForce:
        return replace(self, planet_id=new_planet_id)

    def cast_to_ship(self) -> Ship:
        if not self.is_ship:
            raise NotAShipError(self.__repr__())
        raise NotImplementedError

    def cast_to_ground_force(self) -> GroundForce:
        return self

    def set_is_damaged(self, *, is_damaged: bool) -> GroundForce:
        return replace(self, is_damaged=is_damaged)


unit_stats_lookup: dict[UnitKind, UnitStats] = {
    ShipKind.DESTROYER: UnitStats(cost=1, combat=9, move=2),
    ShipKind.FIGHTER: UnitStats(cost=1, combat=9),
    ShipKind.DREADNOUGHT: UnitStats(
        cost=4,
        combat=5,
        move=1,
        capacity=1,
        unit_abilities=frozenset({UnitAbility.SUSTAIN_DAMAGE}),
    ),
    ShipKind.CARRIER: UnitStats(cost=3, combat=9, move=1, capacity=4),
    ShipKind.CRUISER: UnitStats(cost=2, combat=7, move=2),
    ShipKind.FLAGSHIP: UnitStats(
        cost=8,
        combat=7,
        move=1,
        capacity=3,
        unit_abilities=frozenset({UnitAbility.SUSTAIN_DAMAGE}),
    ),
    ShipKind.WAR_SUN: UnitStats(
        cost=8,
        combat=9,
        move=2,
        capacity=4,
        burst_icons=3,
        unit_abilities=frozenset({UnitAbility.SUSTAIN_DAMAGE}),
    ),
    GroundForceKind.INFANTRY: UnitStats(cost=1, combat=8),
    GroundForceKind.MECH: UnitStats(
        cost=2,
        combat=6,
        unit_abilities=frozenset({UnitAbility.SUSTAIN_DAMAGE}),
    ),
}


def make_unit_with_id(
    unit_id: int,
    owner_name: str,
    kind: UnitKind,
    system_id: int | None = None,
    planet_id: int | None = None,
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
        planet_id=planet_id,
    )
