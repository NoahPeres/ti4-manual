from dataclasses import dataclass, replace
from itertools import product
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.engine.core.command import Command, CommandType
from src.engine.core.event import Event
from src.engine.core.game_engine import CommandResult
from src.engine.core.game_state import (
    GameState,
    HexCoord,
    Planet,
    SpaceCombatStep,
    System,
    TacticalActionStep,
    Window,
)
from src.engine.tokens import CommandToken
from src.engine.units.units import GroundForceKind, ShipKind, Unit, make_unit_with_id
from tests.test_engine.test_lrr.common import (
    make_basic_session_from_players,
    make_player,
    make_tactical_action_movement_state,
    pass_space_cannon_window,
)

if TYPE_CHECKING:
    from src.engine.core.game_session import GameSession


@pytest.mark.parametrize(
    ("units", "expected_tactical_action_step"),
    [
        (frozenset[Unit](), TacticalActionStep.INVASION),
        (
            frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                },
            ),
            TacticalActionStep.INVASION,
        ),
        (
            frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                },
            ),
            TacticalActionStep.SPACE_COMBAT,
        ),
    ],
)
def test_78_1_space_combat_must_occur_iff_more_than_one_player_has_ships_after_space_cannon(
    *,
    units: frozenset[Unit],
    expected_tactical_action_step: TacticalActionStep,
) -> None:
    player_a = make_player(
        name="A",
    )
    player_b = make_player(
        name="B",
    )

    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=units,
            player_names=["A", "B"],
            systems=frozenset(
                {
                    System(
                        id=0,
                        command_tokens=(CommandToken(player_name="A"),),
                        coordinates=HexCoord(x=0, y=0),
                    ),
                },
            ),
        ),
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    assert session.current_state.turn_context.tactical_action_step == expected_tactical_action_step


def test_78_2_ability_at_start_of_space_combat_occurs_before_afb() -> None:
    player_a = make_player(
        name="A",
    )
    player_b = make_player(
        name="B",
    )

    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                },
            ),
            player_names=["A", "B"],
            systems=frozenset(
                {
                    System(
                        id=0,
                        command_tokens=(CommandToken(player_name="A"),),
                        coordinates=HexCoord(x=0, y=0),
                    ),
                },
            ),
        ),
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    for player in (player_a, player_b):
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_START_OF_COMBAT_ROUND),
        )
    assert session.current_state.turn_context.space_combat_context is not None
    assert (
        session.current_state.turn_context.space_combat_context.step
        == SpaceCombatStep.ANTI_FIGHTER_BARRAGE
    )


def test_78_2_a_start_of_first_combat_round_and_start_of_combat_are_the_same_window() -> None:
    player_a = make_player(
        name="A",
    )
    player_b = make_player(
        name="B",
    )

    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                },
            ),
            player_names=["A", "B"],
        ),
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    assert session.current_state.window_context.is_window_active(
        Window.START_OF_FIRST_ROUND_OF_SPACE_COMBAT,
    )
    assert session.current_state.window_context.is_window_active(Window.START_OF_SPACE_COMBAT)


def make_start_of_space_combat_state(initial_state: GameState | None = None) -> GameSession:
    player_a = make_player(
        name="A",
    )
    player_b = make_player(
        name="B",
    )

    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=initial_state
        or make_tactical_action_movement_state(
            active_system_id=0,
            units=frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                },
            ),
            player_names=["A", "B"],
        ),
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    return session


def make_announce_retreat_step_combat_state(initial_state: GameState | None = None) -> GameSession:
    session = make_start_of_space_combat_state(initial_state)
    player_a = session.current_state.get_player("A")
    player_b = session.current_state.get_player("B")
    for player in (player_a, player_b):
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_START_OF_COMBAT_ROUND),
        )
    for player in (player_a, player_b):
        session.apply_command(
            Command(actor=player, command_type=CommandType.USE_ANTI_FIGHTER_BARRAGE),
        )
    return session


class DestroyPlayersShipsInActiveSystem(Event):
    def __init__(self, player_names: list[str]) -> None:
        self.player_names = player_names
        super().__init__()

    def apply(self, previous_state: GameState) -> GameState:
        new_state = previous_state
        for ship in previous_state.get_ships_in_system(
            system_id=previous_state.get_active_system().id,
        ):
            if ship.owner_name in self.player_names:
                new_state = new_state.destroy_unit(unit_id=ship.unit_id)
        return new_state

    def __repr__(self) -> str:
        return f"DestroyAllUnits:{self.player_names}"


@pytest.mark.parametrize(
    "destroy_event",
    [
        DestroyPlayersShipsInActiveSystem(player_names=["A"]),
        DestroyPlayersShipsInActiveSystem(player_names=["B"]),
        DestroyPlayersShipsInActiveSystem(player_names=["A", "B"]),
    ],
)
def test_78_3_a_space_combat_ends_if_one_or_both_players_have_no_ships_after_afb(
    destroy_event: DestroyPlayersShipsInActiveSystem,
) -> None:
    session = make_start_of_space_combat_state()
    player_a = session.current_state.get_player("A")
    player_b = session.current_state.get_player("B")
    for player in (player_a, player_b):
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_START_OF_COMBAT_ROUND),
        )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANTI_FIGHTER_BARRAGE
    )
    session.apply_command_result(
        CommandResult(
            new_state=destroy_event.apply(session.current_state),
            success=True,
            events=[destroy_event],
        ),
    )
    for player in (player_a, player_b):
        session.apply_command(
            Command(actor=player, command_type=CommandType.USE_ANTI_FIGHTER_BARRAGE),
        )
    assert session.current_state.window_context.is_window_active(window=Window.END_OF_SPACE_COMBAT)


def test_78_2_b_end_of_last_combat_round_and_end_of_combat_are_the_same_window() -> None:
    session = make_start_of_space_combat_state()
    player_a = session.current_state.get_player("A")
    assert session.current_state.turn_context.space_combat_context is not None
    assigned_hits = replace(
        session.current_state.turn_context.space_combat_context,
        assigned_hits=frozenset({2}),
        step=SpaceCombatStep.ASSIGN_HITS,
    )
    session.apply_command_result(
        CommandResult(
            new_state=replace(
                session.current_state.close_all_windows(),
                turn_context=replace(
                    session.current_state.turn_context,
                    space_combat_context=assigned_hits,
                ),
            ),
            success=True,
            events=[],
        ),
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_ASSIGN_HITS),
    )
    assert len(session.current_state.get_ships_in_system(0)) == 1
    assert session.current_state.window_context.is_window_active(
        Window.END_OF_SPACE_COMBAT_ROUND,
    )
    assert session.current_state.window_context.is_window_active(Window.END_OF_SPACE_COMBAT)


def test_78_3_b_players_may_roll_afb_iff_the_first_round_of_combat() -> None:
    session = make_start_of_space_combat_state()
    player_a = session.current_state.get_player("A")
    player_b = session.current_state.get_player("B")
    assert (
        session.current_state.turn_context.tactical_action_step == TacticalActionStep.SPACE_COMBAT
    )
    assert session.current_state.turn_context.space_combat_context is not None
    assert session.current_state.turn_context.space_combat_context.round_number == 1
    assert (
        session.current_state.turn_context.space_combat_context.step
        == SpaceCombatStep.ANTI_FIGHTER_BARRAGE
    )
    for player in (player_a, player_b):
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_START_OF_COMBAT_ROUND),
        )

    for player, command_type in product(
        (player_a, player_b),
        (CommandType.USE_ANTI_FIGHTER_BARRAGE, CommandType.PASS_ANTI_FIGHTER_BARRAGE),
    ):
        assert session.engine.apply_command(
            state=session.current_state,
            command=Command(actor=player, command_type=command_type),
        ).success

    second_round = replace(
        session.current_state,
        turn_context=replace(
            session.current_state.turn_context,
            space_combat_context=replace(
                session.current_state.turn_context.space_combat_context,
                round_number=2,
            ),
        ),
    )

    for player in (player_a, player_b):
        assert not session.engine.apply_command(
            state=second_round,
            command=Command(actor=player, command_type=CommandType.USE_ANTI_FIGHTER_BARRAGE),
        ).success


def test_78_3_c_afb_still_occurs_when_no_fighters_present() -> None:
    session = make_start_of_space_combat_state()
    player_a = session.current_state.get_player("A")
    player_b = session.current_state.get_player("B")
    assert all(
        unit.kind != ShipKind.FIGHTER
        for unit in session.current_state.get_units_in_system(
            session.current_state.get_active_system().id,
        )
    )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANTI_FIGHTER_BARRAGE
    )
    for player in (player_a, player_b):
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_START_OF_COMBAT_ROUND),
        )
    assert session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=player_a, command_type=CommandType.USE_ANTI_FIGHTER_BARRAGE),
    ).success


def test_78_3_only_use_afb_once() -> None:
    session = make_start_of_space_combat_state()
    player_a = session.current_state.get_player("A")
    player_b = session.current_state.get_player("B")
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANTI_FIGHTER_BARRAGE
    )
    for player in (player_a, player_b):
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_START_OF_COMBAT_ROUND),
        )
    _ = session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.USE_ANTI_FIGHTER_BARRAGE),
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=player_a, command_type=CommandType.USE_ANTI_FIGHTER_BARRAGE),
    ).success


def test_78_3_advance_to_announce_retreats_step() -> None:
    session = make_start_of_space_combat_state()
    player_a = session.current_state.get_player("A")
    player_b = session.current_state.get_player("B")
    for player in (player_a, player_b):
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_START_OF_COMBAT_ROUND),
        )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANTI_FIGHTER_BARRAGE
    )
    for player in (player_a, player_b):
        session.apply_command(
            Command(actor=player, command_type=CommandType.USE_ANTI_FIGHTER_BARRAGE),
        )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANNOUNCE_RETREATS
    )


def test_78_4_each_player_may_announce_beginning_with_defender() -> None:
    session = make_announce_retreat_step_combat_state()
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANNOUNCE_RETREATS
    )
    attacker = session.current_state.turn_context.get_space_combat_context().attacker
    defender = session.current_state.turn_context.get_space_combat_context().defender

    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=attacker, command_type=CommandType.ANNOUNCE_RETREAT),
    ).success

    session.apply_command(
        command=Command(actor=defender, command_type=CommandType.PASS_ANNOUNCE_RETREAT),
    )
    assert not session.failure_history
    session.apply_command(
        command=Command(actor=attacker, command_type=CommandType.ANNOUNCE_RETREAT),
    )
    assert not session.failure_history
    assert (
        session.current_state.turn_context.get_space_combat_context().declared_retreat == attacker
    )


def test_78_4_a_retreat_does_not_happen_immediately() -> None:
    session = make_announce_retreat_step_combat_state()
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANNOUNCE_RETREATS
    )
    ships_before = session.current_state.get_ships_in_system(
        session.current_state.get_active_system().id,
    )
    attacker = session.current_state.turn_context.get_space_combat_context().attacker
    defender = session.current_state.turn_context.get_space_combat_context().defender

    session.apply_command(
        command=Command(actor=defender, command_type=CommandType.PASS_ANNOUNCE_RETREAT),
    )
    session.apply_command(
        command=Command(actor=attacker, command_type=CommandType.ANNOUNCE_RETREAT),
    )
    assert (
        session.current_state.turn_context.get_space_combat_context().declared_retreat == attacker
    )
    assert ships_before == session.current_state.get_ships_in_system(
        session.current_state.get_active_system().id,
    )


def test_78_4_b_attacker_cannot_announce_retreat_after_defender_does() -> None:
    session = make_announce_retreat_step_combat_state()
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANNOUNCE_RETREATS
    )
    attacker = session.current_state.turn_context.get_space_combat_context().attacker
    defender = session.current_state.turn_context.get_space_combat_context().defender
    session.apply_command(
        command=Command(actor=defender, command_type=CommandType.ANNOUNCE_RETREAT),
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=attacker, command_type=CommandType.ANNOUNCE_RETREAT),
    ).success
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ROLL_DICE
    )


def test_78_4_defender_cannot_announce_twice() -> None:
    session = make_announce_retreat_step_combat_state()
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANNOUNCE_RETREATS
    )
    defender = session.current_state.turn_context.get_space_combat_context().defender
    session.apply_command(
        command=Command(actor=defender, command_type=CommandType.PASS_ANNOUNCE_RETREAT),
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=defender, command_type=CommandType.ANNOUNCE_RETREAT),
    ).success


CENTRE_RING_OF_SYSTEMS = frozenset(
    {
        System(id=0, command_tokens=(), coordinates=HexCoord(0, 0)),
        System(id=1, command_tokens=(), coordinates=HexCoord(1, 0)),
        System(id=2, command_tokens=(), coordinates=HexCoord(0, 1)),
        System(id=3, command_tokens=(), coordinates=HexCoord(-1, 0)),
        System(id=4, command_tokens=(), coordinates=HexCoord(0, -1)),
        System(id=5, command_tokens=(), coordinates=HexCoord(1, 1)),
        System(id=6, command_tokens=(), coordinates=HexCoord(-1, -1)),
    },
)


class InvalidTestConfigError(ValueError):
    pass


@dataclass
class RetreatEligibility:
    has_friendly_units: bool
    has_enemy_ships: bool
    has_controlled_planet: bool

    def __post_init__(self) -> None:
        if self.has_friendly_units and self.has_enemy_ships:
            self.has_friendly_units = False  # can't have both

    @property
    def is_eligible(self) -> bool:
        return not self.has_enemy_ships and (self.has_controlled_planet or self.has_friendly_units)


def set_up_units_and_systems(
    system: System,
    *,
    retreat_eligibility: RetreatEligibility,
) -> tuple[set[Unit], System]:
    units = set[Unit]()
    if retreat_eligibility.has_friendly_units:
        units |= {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=ShipKind.DESTROYER,
                system_id=system.id,
            ),
        }
    if retreat_eligibility.has_enemy_ships:
        units |= {
            make_unit_with_id(
                unit_id=0,
                owner_name="B",
                kind=ShipKind.DESTROYER,
                system_id=system.id,
            ),
        }
    if retreat_eligibility.has_controlled_planet:
        units |= {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=GroundForceKind.INFANTRY,
                system_id=system.id,
                planet_id=system.id,
            ),
        }
    system = replace(system, planets=frozenset({Planet(planet_id=system.id)}))
    return (
        units,
        system,
    )


def parse_setup_seed(
    setup_seed: list[bool],
    systems: set[System],
) -> tuple[set[Unit], set[System], bool]:
    units = set[Unit]()
    new_systems = set[System]()
    all_retreat_eligibility: list[RetreatEligibility] = []
    for i, system in enumerate(systems):
        retreat_eligibility = RetreatEligibility(
            has_friendly_units=setup_seed[3 * i],
            has_enemy_ships=setup_seed[3 * i + 1],
            has_controlled_planet=setup_seed[3 * i + 2],
        )
        all_retreat_eligibility.append(retreat_eligibility)
        new_units, new_system = set_up_units_and_systems(
            system=system,
            retreat_eligibility=retreat_eligibility,
        )
        units |= new_units
        new_systems |= {new_system}
    eligible_system_exists = any(retreat.is_eligible for retreat in all_retreat_eligibility)
    return units, new_systems, eligible_system_exists


no_adjacent_systems = frozenset({System(id=0, command_tokens=(), coordinates=HexCoord(0, 0))})


@given(setup_seed=st.lists(st.booleans(), min_size=18, max_size=18))
def test_78_4_c_player_cannot_retreat_without_adjacent_system(setup_seed: list[bool]) -> None:
    players = (make_player("A"), make_player("B"))
    additional_units, additional_systems, eligible_system_exists = parse_setup_seed(
        setup_seed=setup_seed,
        systems={system for system in CENTRE_RING_OF_SYSTEMS if system.id != 0},
    )
    session = make_announce_retreat_step_combat_state(
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                }
                | additional_units,
            ),
            player_names=[player.name for player in players],
            systems=frozenset(
                {System(id=0, command_tokens=(), coordinates=HexCoord(0, 0))} | additional_systems,
            ),
        ),
    )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANNOUNCE_RETREATS
    )
    defender = session.current_state.turn_context.get_space_combat_context().defender
    attacker = session.current_state.turn_context.get_space_combat_context().attacker
    assert attacker.name == "A"
    session.apply_command(
        command=Command(actor=defender, command_type=CommandType.PASS_ANNOUNCE_RETREAT),
    )
    assert (
        session.engine.apply_command(
            state=session.current_state,
            command=Command(actor=attacker, command_type=CommandType.ANNOUNCE_RETREAT),
        ).success
        == eligible_system_exists
    )
