from dataclasses import dataclass, replace
from itertools import product
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.engine.actions.space_combat import (
    AssignHitCommand,
    CombatRoll,
    RemoveCommandTokenFromPoolCommand,
    RetreatShipCommand,
    RollDiceForUnitEvent,
)
from src.engine.core.command import Command, CommandType
from src.engine.core.dice_roller import DiceRoller
from src.engine.core.event import Event
from src.engine.core.game_engine import CommandResult
from src.engine.core.game_state import (
    Galaxy,
    GameState,
    SpaceCombatStep,
    System,
    TacticalActionStep,
    Window,
)
from src.engine.core.player import MAX_COMMAND_TOKENS, CommandSheet, CommandTokenPool
from src.engine.core.system import HexCoord, Planet
from src.engine.tokens import CommandToken
from src.engine.units.units import GroundForceKind, ShipKind, Unit, make_unit_with_id
from tests.test_engine.test_lrr.common import (
    CENTRE_RING_OF_SYSTEMS,
    grant_all_units_unique_ids,
    make_basic_session_from_players,
    make_player,
    make_tactical_action_movement_state,
    pass_space_cannon_window,
)

if TYPE_CHECKING:
    from src.engine.core.game_session import GameSession
    from src.engine.core.player import Player


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
        command_sheet=CommandSheet.make_from_int(
            player_name="A",
            tactic=2,
            fleet=3,
            strategy=2,
            reinforcements=8,
        ),
    )
    player_b = make_player(
        name="B",
    )

    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=units,
            players=(player_a, player_b),
            systems=Galaxy(
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
        command_sheet=CommandSheet.make_from_int(
            player_name="A",
            tactic=2,
            fleet=3,
            strategy=2,
            reinforcements=8,
        ),
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
            players=(player_a, player_b),
            systems=Galaxy(
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
        command_sheet=CommandSheet.make_from_int(
            player_name="A",
            tactic=2,
            fleet=3,
            strategy=2,
            reinforcements=8,
        ),
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
            players=(player_a, player_b),
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


def make_start_of_space_combat_state(
    initial_state: GameState | None = None,
    dice_roller: DiceRoller | None = None,
) -> GameSession:
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
                    make_unit_with_id(
                        unit_id=3,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=1,
                    ),
                    make_unit_with_id(
                        unit_id=4,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=2,
                    ),
                },
            ),
            players=(player_a, player_b),
            systems=CENTRE_RING_OF_SYSTEMS,
        ),
        dice_roller=dice_roller,
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    return session


def make_announce_retreat_step_combat_state(
    initial_state: GameState | None = None,
    dice_roller: DiceRoller | None = None,
) -> GameSession:
    session = make_start_of_space_combat_state(initial_state, dice_roller)
    player_a = session.current_state.get_player("A")
    player_b = session.current_state.get_player("B")
    for player in session.current_state.players:
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
                new_state = new_state.remove_unit(unit_id=ship.unit_id)
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
    player_b = session.current_state.get_player("B")
    assert session.current_state.turn_context.space_combat_context is not None
    assigned_hits = replace(
        session.current_state.turn_context.space_combat_context,
        attacker_combat_rolls=(CombatRoll(unit_id=1, value=10, hit=True),),
        defender_combat_rolls=(CombatRoll(unit_id=1, value=1, hit=False),),
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
        command=AssignHitCommand(actor=player_b, command_type=CommandType.ASSIGN_HIT, unit_id=2),
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
        session.current_state.turn_context.get_space_combat_context().declared_retreat_name
        == attacker.name
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
        session.current_state.turn_context.get_space_combat_context().declared_retreat_name
        == attacker.name
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


class InvalidTestConfigError(ValueError):
    pass


@dataclass
class RetreatEligibility:
    has_friendly_units: bool
    has_enemy_ships: bool
    has_controlled_planet: bool

    def __post_init__(self) -> None:
        if self.has_friendly_units and self.has_enemy_ships:
            raise InvalidTestConfigError

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
    setup_seed: list[tuple[bool, bool, bool]],
    systems: set[System],
    ref_system: System,
) -> tuple[set[Unit], set[System], bool]:
    units = set[Unit]()
    new_systems = set[System]()
    all_retreat_eligibility: list[RetreatEligibility] = []
    for i, system in enumerate(systems):
        assert system.is_adjacent_to(ref_system)
        retreat_eligibility = RetreatEligibility(
            has_friendly_units=setup_seed[i][0],
            has_enemy_ships=setup_seed[i][1],
            has_controlled_planet=setup_seed[i][2],
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


_VALID_ELIGIBILITY_CONFIGS = [
    (a, b, c) for a, b, c in product([False, True], repeat=3) if not (a and b)
]


@given(
    setup_seed=st.lists(
        st.sampled_from(_VALID_ELIGIBILITY_CONFIGS),
        min_size=6,
        max_size=6,
    ),
)
def test_78_4_c_player_cannot_retreat_without_adjacent_system(
    setup_seed: list[tuple[bool, bool, bool]],
) -> None:
    players = (
        make_player(
            "A",
            command_sheet=CommandSheet.make_from_int(
                player_name="A",
                tactic=2,
                fleet=3,
                strategy=2,
                reinforcements=8,
            ),
        ),
        make_player("B"),
    )

    additional_units, additional_systems, eligible_system_exists = parse_setup_seed(
        setup_seed=setup_seed,
        systems={system for system in CENTRE_RING_OF_SYSTEMS if system.id != 0},
        ref_system=CENTRE_RING_OF_SYSTEMS.get_system(0),
    )
    session = make_announce_retreat_step_combat_state(
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=grant_all_units_unique_ids(
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
                    }
                    | additional_units,
                ),
            ),
            players=players,
            systems=Galaxy(
                {
                    System(
                        id=0,
                        command_tokens=(CommandToken(player_name="A"),),
                        coordinates=HexCoord(0, 0),
                    ),
                }
                | additional_systems,
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
    assert session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=attacker, command_type=CommandType.PASS_ANNOUNCE_RETREAT),
    ).success


def make_roll_dice_step_state(
    units: frozenset[Unit],
    systems: Galaxy | None = None,
    dice_roller: DiceRoller | None = None,
    players: tuple[Player, ...] | None = None,
) -> GameSession:
    if players is None:
        players = (
            make_player(
                "A",
                command_sheet=CommandSheet.make_from_int(
                    player_name="A",
                    tactic=2,
                    fleet=3,
                    strategy=2,
                    reinforcements=8,
                ),
            ),
            make_player("B"),
        )
    session = make_announce_retreat_step_combat_state(
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=units,
            players=players,
            systems=systems
            or Galaxy(
                {
                    System(
                        id=0,
                        command_tokens=(CommandToken(player_name="A"),),
                        coordinates=HexCoord(0, 0),
                        planets=frozenset({Planet(0)}),
                    ),
                },
            ),
        ),
        dice_roller=dice_roller,
    )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANNOUNCE_RETREATS
    )
    defender = session.current_state.turn_context.get_space_combat_context().defender
    attacker = session.current_state.turn_context.get_space_combat_context().attacker
    for player in defender, attacker:
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_ANNOUNCE_RETREAT),
        )
    return session


class FixedDiceRoller(DiceRoller):
    def __init__(self, value: int) -> None:
        self.value = value

    def roll(self, num_dice: int) -> list[int]:
        return [self.value] * num_dice


@given(
    attacker_unit_types=st.lists(
        st.sampled_from([ShipKind.DESTROYER, ShipKind.CRUISER, ShipKind.DREADNOUGHT]),
        min_size=1,
        max_size=16,
    ),
    defender_unit_types=st.lists(
        st.sampled_from([ShipKind.DESTROYER, ShipKind.CRUISER, ShipKind.DREADNOUGHT]),
        min_size=1,
        max_size=16,
    ),
)
def test_78_5_roll_dice_step_one_roll_per_ship(
    attacker_unit_types: list[ShipKind],
    defender_unit_types: list[ShipKind],
) -> None:
    all_units = set[Unit]()
    for i, unit_type in enumerate(attacker_unit_types):
        all_units |= {make_unit_with_id(unit_id=i, owner_name="A", kind=unit_type, system_id=0)}
    next_id = len(all_units)
    for i, unit_type in enumerate(defender_unit_types):
        all_units |= {
            make_unit_with_id(unit_id=next_id + i, owner_name="B", kind=unit_type, system_id=0),
        }
    session = make_roll_dice_step_state(
        units=frozenset(all_units),
        dice_roller=FixedDiceRoller(value=5),
    )
    session.apply_command(
        Command(
            session.current_state.turn_context.get_space_combat_context().attacker,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    session.apply_command(
        Command(
            session.current_state.turn_context.get_space_combat_context().defender,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    attacker, defender = (
        space_combat_context.attacker,
        space_combat_context.defender,
    )
    assert len(space_combat_context.get_combat_rolls_for_player(attacker)) == len(
        attacker_unit_types,
    )
    assert len(space_combat_context.get_combat_rolls_for_player(defender)) == len(
        defender_unit_types,
    )
    assert space_combat_context.total_hits_for_player(attacker) == len(
        [ship for ship in attacker_unit_types if ship == ShipKind.DREADNOUGHT],
    )
    assert space_combat_context.total_hits_for_player(defender) == len(
        [ship for ship in defender_unit_types if ship == ShipKind.DREADNOUGHT],
    )


def test_78_5_ground_forces_do_not_roll_space_combat() -> None:
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=GroundForceKind.INFANTRY,
                system_id=0,
                planet_id=0,
            ),
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
    )
    session = make_roll_dice_step_state(units=units, dice_roller=FixedDiceRoller(value=5))
    session.apply_command(
        Command(
            session.current_state.turn_context.get_space_combat_context().attacker,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    session.apply_command(
        Command(
            session.current_state.turn_context.get_space_combat_context().defender,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    attacker, defender = (
        space_combat_context.attacker,
        space_combat_context.defender,
    )
    assert len(space_combat_context.get_combat_rolls_for_player(attacker)) == 1
    assert len(space_combat_context.get_combat_rolls_for_player(defender)) == 1


def test_78_5_cannot_roll_combat_dice_more_than_once_per_step() -> None:
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=ShipKind.DESTROYER,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=1,
                owner_name="B",
                kind=ShipKind.DESTROYER,
                system_id=0,
            ),
        },
    )
    session = make_roll_dice_step_state(units=units, dice_roller=FixedDiceRoller(value=5))
    attacker = session.current_state.turn_context.get_space_combat_context().attacker
    defender = session.current_state.turn_context.get_space_combat_context().defender
    session.apply_command(
        Command(
            attacker,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=attacker, command_type=CommandType.MAKE_COMBAT_ROLLS),
    ).success
    session.apply_command(
        Command(
            defender,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=defender, command_type=CommandType.MAKE_COMBAT_ROLLS),
    ).success


@given(dice_value=st.integers(min_value=1, max_value=10))
def test_78_5_hit_produced_iff_roll_geq_combat_value(dice_value: int) -> None:
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=ShipKind.DESTROYER,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=1,
                owner_name="B",
                kind=ShipKind.DREADNOUGHT,
                system_id=0,
            ),
        },
    )
    session = make_roll_dice_step_state(units=units, dice_roller=FixedDiceRoller(value=dice_value))
    attacker = session.current_state.turn_context.get_space_combat_context().attacker
    defender = session.current_state.turn_context.get_space_combat_context().defender
    session.apply_command(
        Command(
            attacker,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    session.apply_command(
        Command(
            defender,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    _destroyer_combat_value = 9
    _dreadnought_combat_value = 5
    assert space_combat_context.total_hits_for_player(attacker) == (
        dice_value >= _destroyer_combat_value
    )
    assert space_combat_context.total_hits_for_player(defender) == (
        dice_value >= _dreadnought_combat_value
    )


def test_78_5_other_players_cannot_make_combat_rolls() -> None:
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=ShipKind.DESTROYER,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=1,
                owner_name="B",
                kind=ShipKind.DESTROYER,
                system_id=0,
            ),
        },
    )
    session = make_roll_dice_step_state(
        players=(
            make_player(
                "A",
                command_sheet=CommandSheet.make_from_int(
                    player_name="A",
                    tactic=2,
                    fleet=3,
                    strategy=2,
                    reinforcements=8,
                ),
            ),
            make_player("B"),
            make_player("C"),
        ),
        units=units,
        dice_roller=FixedDiceRoller(value=5),
    )
    other_player = session.current_state.get_player("C")

    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=other_player, command_type=CommandType.MAKE_COMBAT_ROLLS),
    ).success


def test_78_5_a_burst_icons_mean_extra_dice() -> None:
    _war_sun_burst_icons = 3
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=ShipKind.WAR_SUN,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=1,
                owner_name="B",
                kind=ShipKind.WAR_SUN,
                system_id=0,
            ),
        },
    )
    session = make_roll_dice_step_state(
        units=units,
        dice_roller=FixedDiceRoller(value=5),
    )
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    attacker = space_combat_context.attacker
    defender = space_combat_context.defender
    session.apply_command(
        Command(
            actor=attacker,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    session.apply_command(
        Command(
            actor=defender,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    assert len(space_combat_context.get_combat_rolls_for_player(attacker)) == _war_sun_burst_icons
    assert len(space_combat_context.get_combat_rolls_for_player(defender)) == _war_sun_burst_icons


def test_75_b_c_dice_are_rolled_in_increasing_order() -> None:
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=i,
                owner_name="A",
                kind=kind,
                system_id=0,
            )
            for i, kind in enumerate(ShipKind)
        }
        | {
            make_unit_with_id(
                unit_id=len(ShipKind),
                owner_name="B",
                kind=ShipKind.DREADNOUGHT,
                system_id=0,
            ),
        },
    )
    expected_order = sorted(
        [unit for unit in units if unit.owner_name == "A"],
        key=lambda unit: (unit.stats.combat, unit.unit_id),
    )
    session = make_roll_dice_step_state(units=units, dice_roller=FixedDiceRoller(value=5))
    attacker = session.current_state.turn_context.get_space_combat_context().attacker
    session.apply_command(
        Command(
            attacker,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )
    latest_events = session.history[-1].events
    rolled_unit_ids: list[int] = []
    for event in latest_events:
        if isinstance(event, RollDiceForUnitEvent) and event.unit_id not in rolled_unit_ids:
            rolled_unit_ids.append(event.unit_id)
    assert rolled_unit_ids == [unit.unit_id for unit in expected_order]


@pytest.mark.skip
def test_78_5_e_abilities_after_dice_rolled_trigger_after_all_combat_rolls_made() -> None:
    pass


def test_78_5_f_attacker_rolls_first() -> None:
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=ShipKind.DESTROYER,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=1,
                owner_name="B",
                kind=ShipKind.DESTROYER,
                system_id=0,
            ),
        },
    )
    session = make_roll_dice_step_state(units=units, dice_roller=FixedDiceRoller(value=5))
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    attacker = space_combat_context.attacker
    defender = space_combat_context.defender
    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=defender, command_type=CommandType.MAKE_COMBAT_ROLLS),
    ).success
    session.apply_command(
        Command(
            actor=attacker,
            command_type=CommandType.MAKE_COMBAT_ROLLS,
        ),
    )


@given(n_hits=st.integers(min_value=1, max_value=10))
def test_78_6_destroy_one_ship_per_opponent_hit(n_hits: int) -> None:
    max_hits = 10
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=i,
                owner_name="A",
                kind=ShipKind.DESTROYER,
                system_id=0,
            )
            for i in range(max_hits)
        }
        | {
            make_unit_with_id(
                unit_id=max_hits + i,
                owner_name="B",
                kind=ShipKind.DREADNOUGHT,
                system_id=0,
            )
            for i in range(n_hits)
        },
    )
    session = make_roll_dice_step_state(units=units, dice_roller=FixedDiceRoller(value=5))
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    attacker = space_combat_context.attacker
    defender = space_combat_context.defender
    for player in (attacker, defender):
        session.apply_command(
            Command(
                actor=player,
                command_type=CommandType.MAKE_COMBAT_ROLLS,
            ),
        )
    session.apply_command(Command(actor=attacker, command_type=CommandType.PASS_BEFORE_ASSIGN_HITS))
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    assert space_combat_context.total_hits_for_player(attacker) == 0
    assert space_combat_context.total_hits_for_player(defender) == n_hits
    assert space_combat_context.step == SpaceCombatStep.ASSIGN_HITS
    assert not session.engine.apply_command(
        state=session.current_state,
        command=AssignHitCommand(
            actor=attacker,
            command_type=CommandType.ASSIGN_HIT,
            unit_id=10,  # Enemy ship
        ),
    ).success
    for i in range(n_hits):
        session.apply_command(
            AssignHitCommand(
                actor=attacker,
                command_type=CommandType.ASSIGN_HIT,
                unit_id=i,  # Friendly ship
            ),
        )
        assert len(session.failure_history) == 0
    assert (
        len(session.current_state.get_ships_in_system(0, player_name=attacker.name))
        == max_hits - n_hits
    )
    if n_hits < max_hits:
        assert (
            session.current_state.turn_context.get_space_combat_context().step
            == SpaceCombatStep.RETREAT
        )


def test_78_6_assign_hit_legality_edge_cases() -> None:
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=ShipKind.DREADNOUGHT,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=3,
                owner_name="A",
                kind=ShipKind.CRUISER,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=5,
                owner_name="A",
                kind=ShipKind.CRUISER,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=1,
                owner_name="B",
                kind=ShipKind.DREADNOUGHT,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=4,
                owner_name="B",
                kind=ShipKind.DREADNOUGHT,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=2,
                owner_name="A",
                kind=ShipKind.DREADNOUGHT,
                system_id=1,
            ),
        },
    )
    session = make_roll_dice_step_state(units=units, dice_roller=FixedDiceRoller(value=5))
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    attacker = space_combat_context.attacker
    defender = space_combat_context.defender
    for player in (attacker, defender):
        session.apply_command(
            Command(
                actor=player,
                command_type=CommandType.MAKE_COMBAT_ROLLS,
            ),
        )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ASSIGN_HITS
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=AssignHitCommand(actor=defender, command_type=CommandType.ASSIGN_HIT, unit_id=1),
    ).success  # attacker assigns first
    assert not session.engine.apply_command(
        state=session.current_state,
        command=AssignHitCommand(actor=attacker, command_type=CommandType.ASSIGN_HIT, unit_id=2),
    ).success  # not in active system
    session.apply_command(
        command=AssignHitCommand(actor=attacker, command_type=CommandType.ASSIGN_HIT, unit_id=0),
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=AssignHitCommand(actor=attacker, command_type=CommandType.ASSIGN_HIT, unit_id=0),
    ).success  # Ship already destroyed
    session.apply_command(
        command=AssignHitCommand(actor=attacker, command_type=CommandType.ASSIGN_HIT, unit_id=3),
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=AssignHitCommand(actor=attacker, command_type=CommandType.ASSIGN_HIT, unit_id=5),
    ).success  # no remaining hits to assign


def test_78_6_a_window_before_assigning_hits_for_sustain_damage() -> None:
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=ShipKind.DREADNOUGHT,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=1,
                owner_name="B",
                kind=ShipKind.DREADNOUGHT,
                system_id=0,
            ),
        },
    )
    session = make_roll_dice_step_state(units=units, dice_roller=FixedDiceRoller(value=5))
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    attacker = space_combat_context.attacker
    defender = space_combat_context.defender
    for player in (attacker, defender):
        session.apply_command(
            Command(
                actor=player,
                command_type=CommandType.MAKE_COMBAT_ROLLS,
            ),
        )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ASSIGN_HITS
    )
    assert Window.BEFORE_ASSIGNING_HITS in session.current_state.window_context.active_windows
    assert session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=attacker, command_type=CommandType.PASS_BEFORE_ASSIGN_HITS),
    ).success


def test_78_6_b_after_assignment_units_are_in_reinforcements() -> None:
    units = frozenset(
        {
            make_unit_with_id(
                unit_id=0,
                owner_name="A",
                kind=ShipKind.DREADNOUGHT,
                system_id=0,
            ),
            make_unit_with_id(
                unit_id=1,
                owner_name="B",
                kind=ShipKind.DREADNOUGHT,
                system_id=0,
            ),
        },
    )
    session = make_roll_dice_step_state(units=units, dice_roller=FixedDiceRoller(value=5))
    space_combat_context = session.current_state.turn_context.get_space_combat_context()
    attacker = space_combat_context.attacker
    defender = space_combat_context.defender
    for player in (attacker, defender):
        session.apply_command(
            Command(
                actor=player,
                command_type=CommandType.MAKE_COMBAT_ROLLS,
            ),
        )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ASSIGN_HITS
    )
    session.apply_command(
        command=Command(actor=attacker, command_type=CommandType.PASS_BEFORE_ASSIGN_HITS),
    )
    session.apply_command(
        command=AssignHitCommand(actor=attacker, command_type=CommandType.ASSIGN_HIT, unit_id=0),
    )
    assert 0 in [unit.unit_id for unit in session.current_state.reinforcements_for_player(attacker)]


def test_78_7_a_combat_immediately_ends_when_only_one_player_has_units() -> None:
    players = (make_player("A"), make_player("B"))
    session = make_announce_retreat_step_combat_state(
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=frozenset(
                {
                    make_unit_with_id(
                        unit_id=0,
                        owner_name="A",
                        kind=ShipKind.DREADNOUGHT,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=1,
                    ),
                },
            ),
            players=players,
            systems=CENTRE_RING_OF_SYSTEMS,
        ),
        dice_roller=FixedDiceRoller(5),
    )
    session.apply_command(
        command=Command(
            actor=session.current_state.get_player("B"),
            command_type=CommandType.ANNOUNCE_RETREAT,
        ),
    )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ROLL_DICE
    )
    context = session.current_state.turn_context.get_space_combat_context()
    for player in [context.attacker, context.defender]:
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.MAKE_COMBAT_ROLLS),
        )
    session.apply_command(
        command=Command(actor=context.defender, command_type=CommandType.PASS_BEFORE_ASSIGN_HITS),
    )
    session.apply_command(
        command=AssignHitCommand(
            actor=context.defender,
            command_type=CommandType.ASSIGN_HIT,
            unit_id=1,
        ),
    )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ASSIGN_HITS  # NOT retreat step
    )
    assert session.current_state.window_context.is_window_active(Window.END_OF_SPACE_COMBAT)


def make_retreat_step_combat_state(
    b_assigns_hit_to: int,
    players: tuple[Player, ...] | None = None,
) -> GameSession:
    if players is None:
        players = (make_player("A"), make_player("B"))
    session = make_announce_retreat_step_combat_state(
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=frozenset(
                {
                    make_unit_with_id(
                        unit_id=0,
                        owner_name="A",
                        kind=ShipKind.DREADNOUGHT,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=1,
                    ),
                    make_unit_with_id(
                        unit_id=3,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=4,
                        owner_name="B",
                        kind=ShipKind.FIGHTER,
                        system_id=0,
                    ),
                },
            ),
            players=players,
            systems=CENTRE_RING_OF_SYSTEMS,
        ),
        dice_roller=FixedDiceRoller(5),
    )
    session.apply_command(
        command=Command(
            actor=session.current_state.get_player("B"),
            command_type=CommandType.ANNOUNCE_RETREAT,
        ),
    )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ROLL_DICE
    )
    context = session.current_state.turn_context.get_space_combat_context()
    for player in [context.attacker, context.defender]:
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.MAKE_COMBAT_ROLLS),
        )
    session.apply_command(
        command=Command(actor=context.defender, command_type=CommandType.PASS_BEFORE_ASSIGN_HITS),
    )
    session.apply_command(
        command=AssignHitCommand(
            actor=context.defender,
            command_type=CommandType.ASSIGN_HIT,
            unit_id=b_assigns_hit_to,
        ),
    )
    assert len(session.failure_history) == 0
    return session


def test_78_7_b_successful_retreat_moves_all_ships_to_adjacent_system() -> None:
    session = make_retreat_step_combat_state(b_assigns_hit_to=1)
    context = session.current_state.turn_context.get_space_combat_context()
    session.apply_command(
        command=RetreatShipCommand(
            actor=context.defender,
            command_type=CommandType.RETREAT_SHIP,
            ship_id=3,
            to_system_id=1,
        ),
    )
    session.apply_command(
        command=Command(actor=context.defender, command_type=CommandType.END_RETREAT),
    )
    assert len(session.failure_history) == 0
    retreating_ship = session.current_state.get_unit_from_id(3)
    assert retreating_ship in session.current_state.get_ships_in_system(1)


def test_78_7_b_other_players_cannot_end_retreat_command() -> None:
    session = make_retreat_step_combat_state(b_assigns_hit_to=1)
    context = session.current_state.turn_context.get_space_combat_context()
    session.apply_command(
        command=RetreatShipCommand(
            actor=context.defender,
            command_type=CommandType.RETREAT_SHIP,
            ship_id=3,
            to_system_id=1,
        ),
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=context.attacker, command_type=CommandType.END_RETREAT),
    ).success


def test_78_7_b_cannot_retreat_same_ship_twice() -> None:
    session = make_retreat_step_combat_state(b_assigns_hit_to=1)
    context = session.current_state.turn_context.get_space_combat_context()
    session.apply_command(
        command=RetreatShipCommand(
            actor=context.defender,
            command_type=CommandType.RETREAT_SHIP,
            ship_id=3,
            to_system_id=1,
        ),
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=RetreatShipCommand(
            actor=context.defender,
            command_type=CommandType.RETREAT_SHIP,
            ship_id=3,
            to_system_id=1,
        ),
    ).success


def test_78_7_b_retreat_validity() -> None:
    session = make_retreat_step_combat_state(b_assigns_hit_to=1)
    context = session.current_state.turn_context.get_space_combat_context()
    assert not session.engine.apply_command(
        state=session.current_state,
        command=RetreatShipCommand(
            actor=context.defender,
            command_type=CommandType.RETREAT_SHIP,
            ship_id=2,  # ship not in system
            to_system_id=1,
        ),
    ).success
    assert not session.engine.apply_command(
        state=session.current_state,
        command=RetreatShipCommand(
            actor=context.defender,
            command_type=CommandType.RETREAT_SHIP,
            ship_id=1,  # ship is destroyed
            to_system_id=1,
        ),
    ).success
    assert not session.engine.apply_command(
        state=session.current_state,
        command=RetreatShipCommand(
            actor=context.defender,
            command_type=CommandType.RETREAT_SHIP,
            ship_id=4,  # fighter does not have a move value
            to_system_id=1,
        ),
    ).success
    assert not session.engine.apply_command(
        state=session.current_state,
        command=RetreatShipCommand(
            actor=context.attacker,  # not the retreating player
            command_type=CommandType.RETREAT_SHIP,
            ship_id=0,
            to_system_id=1,
        ),
    ).success
    # Note that only system 1 is a legal system, as it contains one of B's ships:
    assert all(
        session.engine.apply_command(
            state=session.current_state,
            command=RetreatShipCommand(
                actor=context.defender,
                command_type=CommandType.RETREAT_SHIP,
                ship_id=3,
                to_system_id=system.id,
            ),
        ).success
        == (system.id == 1)
        for system in CENTRE_RING_OF_SYSTEMS
    )


def test_78_7_b_retreating_player_must_take_all_ships() -> None:
    session = make_retreat_step_combat_state(b_assigns_hit_to=1)
    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(
            actor=session.current_state.turn_context.get_space_combat_context().defender,
            command_type=CommandType.END_RETREAT,
        ),
    ).success  # B's destroyer is still alive in the active system


def test_78_7_b_abandoned_fighters_are_removed() -> None:
    session = make_retreat_step_combat_state(b_assigns_hit_to=1)
    context = session.current_state.turn_context.get_space_combat_context()
    assert any(
        ship.kind == ShipKind.FIGHTER
        for ship in session.current_state.get_ships_in_system(
            system_id=0, player_name=context.defender.name
        )
    )
    session.apply_command(
        command=RetreatShipCommand(
            actor=context.defender,
            command_type=CommandType.RETREAT_SHIP,
            ship_id=3,
            to_system_id=1,
        ),
    )
    session.apply_command(
        command=Command(actor=context.defender, command_type=CommandType.END_RETREAT),
    )
    assert not any(
        ship.kind == ShipKind.FIGHTER
        for ship in session.current_state.get_ships_in_system(
            system_id=1, player_name=context.defender.name
        )
    )
    assert not any(
        ship.kind == ShipKind.FIGHTER
        for ship in session.current_state.get_ships_in_system(
            system_id=session.current_state.get_active_system().id,
            player_name=context.defender.name,
        )
    )


def test_78_7_d_retreating_player_must_place_command_token() -> None:
    session = make_retreat_step_combat_state(b_assigns_hit_to=1)
    context = session.current_state.turn_context.get_space_combat_context()
    session.apply_command(
        command=RetreatShipCommand(
            actor=context.defender,
            command_type=CommandType.RETREAT_SHIP,
            ship_id=3,
            to_system_id=1,
        ),
    )
    session.apply_command(
        command=Command(actor=context.defender, command_type=CommandType.END_RETREAT),
    )
    assert len(session.failure_history) == 0
    defender_command_sheet = session.current_state.get_player(context.defender.name).command_sheet
    assert (
        len(defender_command_sheet.tactic)
        + len(defender_command_sheet.fleet)
        + len(defender_command_sheet.strategy)
        < MAX_COMMAND_TOKENS
    )  # confirm the player would not be forced to remove from sheet, no player decision is required
    assert session.current_state.galaxy.get_system(1).has_command_token(context.defender)


def test_78_7_d_retreating_player_must_place_command_token_even_if_none_in_reinforcements() -> None:
    session = make_retreat_step_combat_state(
        b_assigns_hit_to=1,
        players=(
            make_player("A"),
            make_player(
                "B",
                command_sheet=CommandSheet.make_from_int(
                    player_name="B",
                    tactic=8,
                    fleet=8,
                    strategy=0,
                ),
            ),
        ),
    )
    context = session.current_state.turn_context.get_space_combat_context()
    session.apply_command(
        command=RetreatShipCommand(
            actor=context.defender,
            command_type=CommandType.RETREAT_SHIP,
            ship_id=3,
            to_system_id=1,
        ),
    )
    session.apply_command(
        command=Command(actor=context.defender, command_type=CommandType.END_RETREAT),
    )
    assert len(session.failure_history) == 0
    defender_command_sheet = session.current_state.get_player(context.defender.name).command_sheet
    assert (
        len(defender_command_sheet.tactic)
        + len(defender_command_sheet.fleet)
        + len(defender_command_sheet.strategy)
        == MAX_COMMAND_TOKENS
    )  # player decision is required, they must choose a pool
    assert (
        Window.MUST_CHOOSE_POOL_FOR_REMOVE_COMMAND_TOKEN
        in session.current_state.window_context.active_windows
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=RemoveCommandTokenFromPoolCommand(
            actor=context.attacker,  # Not the retreating player
            command_type=CommandType.REMOVE_COMMAND_TOKEN_FROM_POOL,
            pool=CommandTokenPool.TACTIC,
        ),
    ).success
    assert not session.engine.apply_command(
        state=session.current_state,
        command=RemoveCommandTokenFromPoolCommand(
            actor=context.defender,
            command_type=CommandType.REMOVE_COMMAND_TOKEN_FROM_POOL,
            pool=CommandTokenPool.STRATEGY,  # No tokens in this pool
        ),
    ).success
    session.apply_command(
        RemoveCommandTokenFromPoolCommand(
            actor=context.defender,
            command_type=CommandType.REMOVE_COMMAND_TOKEN_FROM_POOL,
            pool=CommandTokenPool.TACTIC,
        ),
    )
    assert len(session.failure_history) == 0
    assert (
        Window.MUST_CHOOSE_POOL_FOR_REMOVE_COMMAND_TOKEN
        not in session.current_state.window_context.active_windows
    )
    assert session.current_state.galaxy.get_system(1).has_command_token(context.defender)
