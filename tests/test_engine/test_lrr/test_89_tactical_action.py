from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.engine.actions.invasion import CommitGroundForceCommand
from src.engine.core.command import Command, CommandType
from src.engine.core.game_engine import CommandResult
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import (
    Galaxy,
    GameState,
    Phase,
    RetreatDeclaration,
    SpaceCombatContext,
    SpaceCombatStep,
    TacticalActionStep,
    TurnContext,
    Window,
)
from src.engine.core.player import CommandSheet
from src.engine.core.system import HexCoord, Planet, System
from src.engine.strategy_cards import StrategyCard
from src.engine.tokens import CommandToken
from src.engine.units.units import (
    GroundForceKind,
    ShipKind,
    Unit,
    UnitKind,
    make_unit_with_id,
)
from tests.test_engine.test_lrr.common import (
    CENTRE_RING_OF_SYSTEMS,
    CENTRE_RING_OF_SYSTEMS_WITH_PLAYER_A_TOKEN,
    action_command,
    activate_command,
    begin_invasion,
    build_game_state,
    end_movement,
    get_default_game_engine,
    grant_all_units_unique_ids,
    make_basic_session_from_players,
    make_centre_ring_with_player_token,
    make_movement_session,
    make_player,
    make_session,
    make_tactical_action_movement_state,
    move_command,
    pass_bombardment_window,
    resolve_space_cannon,
)


@pytest.mark.parametrize(
    ("tokens", "expected_success"),
    [
        ((), True),
        ((CommandToken(player_name="A"),), False),
        ((CommandToken(player_name="B"),), True),
    ],
)
def test_89_1_active_player_must_activate_system_without_their_command_token(
    *,
    tokens: tuple[CommandToken, ...],
    expected_success: bool,
) -> None:
    player_a = make_player(
        "A",
        command_sheet=CommandSheet.make_from_int(
            player_name="A",
            tactic=2,
            fleet=3,
            strategy=2,
            reinforcements=8,
        )
        if "A" in (token.player_name for token in tokens)
        else None,
    )
    player_b = make_player(
        "B",
        command_sheet=CommandSheet.make_from_int(
            player_name="B",
            tactic=2,
            fleet=3,
            strategy=2,
            reinforcements=8,
        )
        if "B" in (token.player_name for token in tokens)
        else None,
    )
    system = System(id=0, command_tokens=tokens)
    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=GameState(
            players=(player_a, player_b),
            active_player_name=player_a.name,
            phase=Phase.ACTION,
            galaxy=Galaxy({system}),
        ),
    )

    assert (
        session.engine.apply_command(
            state=session.current_state,
            command=activate_command(actor=player_a.name, system_id=0),
        ).success
        is expected_success
    )


def test_89_1_a_active_player_places_token_from_tactic_pool() -> None:
    player_a = make_player("A")
    session = make_basic_session_from_players(players=(player_a,))

    new_state = session.apply_command(command=activate_command(actor=player_a.name, system_id=0))

    activated_system = new_state.galaxy.get_system(system_id=0)
    assert activated_system is not None
    assert any(token.player_name == player_a.name for token in activated_system.command_tokens)


def test_89_1_a_that_system_is_the_active_system() -> None:
    player_a = make_player("A")
    session = make_basic_session_from_players(players=(player_a,))

    new_state = session.apply_command(command=activate_command(actor=player_a.name, system_id=0))

    assert new_state.turn_context.active_system_id == 0


def test_89_1_b_other_players_tokens_do_not_prevent_activation() -> None:
    player_a = make_player("A")
    player_b = make_player(
        "B",
        command_sheet=CommandSheet.make_from_int(
            player_name="B",
            tactic=2,
            fleet=3,
            strategy=2,
            reinforcements=8,
        ),
    )
    system_with_b_token = System(id=0, command_tokens=(CommandToken(player_name=player_b.name),))
    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=GameState(
            players=(player_a, player_b),
            active_player_name=player_a.name,
            phase=Phase.ACTION,
            galaxy=Galaxy({system_with_b_token}),
        ),
    )

    assert session.engine.apply_command(
        state=session.current_state,
        command=activate_command(actor=player_a.name, system_id=0),
    ).success


def test_89_1_advance_to_movement_after_activation() -> None:
    player_a = make_player("A")
    session = make_basic_session_from_players(players=(player_a,))

    new_state = session.apply_command(command=activate_command(actor=player_a.name, system_id=0))

    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT


def test_89_2_only_active_player_moves_ships() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    session = make_session(
        players=(player_a, player_b),
        units=frozenset(
            {
                make_unit_with_id(
                    unit_id=0,
                    owner_name="A",
                    kind=ShipKind.DREADNOUGHT,
                    system_id=0,
                ),
            },
        ),
    )

    result = session.engine.apply_command(
        state=session.current_state,
        command=move_command(actor=player_b.name, ship_id=0, to_system_id=0)[0],
    )

    assert not result.success


def test_89_2_active_player_may_move_only_their_ships() -> None:
    ship = make_unit_with_id(unit_id=0, owner_name="B", kind=ShipKind.DREADNOUGHT, system_id=1)
    player_a = make_player("A")
    player_b = make_player("B")
    session = make_session(
        players=(player_a, player_b),
        units=frozenset({ship}),
    )

    active_system = session.current_state.active_system
    assert active_system is not None

    result = session.engine.apply_command(
        state=session.current_state,
        command=move_command(actor=player_a.name, ship_id=0, to_system_id=active_system.id)[0],
    )

    assert not result.success


def test_89_2_may_not_move_ships_from_systems_with_command_tokens() -> None:
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=1)
    player_a = make_player(
        "A",
        command_sheet=CommandSheet.make_from_int(
            "A",
            tactic=2,
            fleet=3,
            strategy=2,
            reinforcements=8,
        ),
    )
    session = make_session(
        players=(player_a,),
        galaxy=Galaxy(
            {
                System(id=0, command_tokens=()),
                System(id=1, command_tokens=(CommandToken(player_name="A"),)),
            },
        ),
        units=frozenset({ship}),
    )

    active_system = session.current_state.active_system
    assert active_system is not None

    result = session.engine.apply_command(
        state=session.current_state,
        command=move_command(actor=player_a.name, ship_id=0, to_system_id=active_system.id)[0],
    )

    assert not result.success


def test_89_2_ships_with_insufficient_move_cannot_move() -> None:
    state = make_tactical_action_movement_state(active_system_id=2)
    engine = get_default_game_engine()

    result = engine.apply_command(
        state=state,
        command=move_command(actor="A", ship_id=0, to_system_id=2)[0],
    )

    assert not result.success
    assert len(result.new_state.turn_context.pending_moves) == 0


def test_89_2_ship_with_sufficient_move_may_move() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()

    result = engine.apply_command(
        state=state,
        command=move_command(actor="A", ship_id=0, to_system_id=1)[0],
    )

    assert result.success
    assert len(result.new_state.turn_context.pending_moves) == 1


def test_89_2_move_into_active_system() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()

    result = engine.apply_command(
        state=state,
        command=move_command(actor="A", ship_id=0, to_system_id=1)[0],
    )

    move = next(iter(result.new_state.turn_context.pending_moves))
    assert move.to_system_id == 1


def test_89_2_cannot_move_into_non_active_system() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()

    result = engine.apply_command(
        state=state,
        command=move_command(actor="A", ship_id=0, to_system_id=2)[0],
    )

    assert not result.success
    assert len(result.new_state.turn_context.pending_moves) == 0


def test_89_2_a_ships_with_capacity_can_transport_other_units() -> None:
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=0)
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    session = make_movement_session(
        units=frozenset({ship, ground_force}),
        galaxy=CENTRE_RING_OF_SYSTEMS,
    )

    for command in move_command(
        actor="A",
        ship_id=0,
        to_system_id=1,
        transported_unit_ids=frozenset({ground_force.unit_id}),
    ):
        session.apply_command(command=command)

        assert len(session.failure_history) == 0
    assert len(session.current_state.turn_context.pending_moves) == len({ship, ground_force})


def test_89_2_a_ships_with_no_capacity_cannot_transport_other_units() -> None:
    engine = get_default_game_engine()
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DESTROYER, system_id=0)
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    session = make_movement_session(
        units=frozenset({ship, ground_force}),
        galaxy=CENTRE_RING_OF_SYSTEMS,
    )

    move_attempt = move_command(
        actor="A",
        ship_id=0,
        to_system_id=1,
        transported_unit_ids=frozenset({ground_force.unit_id}),
    )
    session.apply_command(command=move_attempt[0])
    assert len(session.failure_history) == 0

    result = engine.apply_command(
        state=session.current_state,
        command=move_attempt[1],
    )

    assert not result.success


def test_89_2_a_ships_with_insufficient_capacity_cannot_transport() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=0)
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    fighter = make_unit_with_id(unit_id=2, owner_name="A", kind=ShipKind.FIGHTER, system_id=0)
    state = replace(state, units=frozenset({ship, ground_force, fighter}))
    move_attempt = move_command(
        actor="A",
        ship_id=0,
        to_system_id=1,
        transported_unit_ids=frozenset({ground_force.unit_id, fighter.unit_id}),
    )
    result = engine.apply_command(state=state, command=move_attempt[0])
    assert result.success  # Dread is fine
    result = engine.apply_command(state=result.new_state, command=move_attempt[1])
    assert result.success  # first capacity is fine
    result = engine.apply_command(state=result.new_state, command=move_attempt[2])
    assert not result.success  # Dread only has a single capacity


@given(transported_unit_kind=st.sampled_from(list(ShipKind) + list(GroundForceKind)))
def test_89_2_a_valid_unit_types_for_transport(
    transported_unit_kind: UnitKind,
) -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=0)

    transported_unit = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=transported_unit_kind,
        system_id=0,
    )
    state = replace(state, units=frozenset({ship, transported_unit}))
    attempted_move = move_command(
        actor="A",
        ship_id=0,
        to_system_id=1,
        transported_unit_ids=frozenset({transported_unit.unit_id}),
    )
    result = engine.apply_command(
        state=state,
        command=attempted_move[0],
    )
    final_result = engine.apply_command(
        state=result.new_state,
        command=attempted_move[1],
    )

    if transported_unit_kind == ShipKind.FIGHTER or isinstance(
        transported_unit_kind,
        GroundForceKind,
    ):
        assert final_result.success
    else:
        assert not final_result.success


def test_89_2_a_player_may_transport_no_units() -> None:
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DESTROYER, system_id=0)

    session = make_movement_session(units=frozenset({ship}), galaxy=CENTRE_RING_OF_SYSTEMS)

    session.apply_command(
        command=move_command(
            actor="A",
            ship_id=0,
            to_system_id=1,
        )[0],
    )

    assert len(session.failure_history) == 0
    assert not session.current_state.window_context.is_window_active(Window.TRANSPORT_UNITS)
    assert len(session.current_state.turn_context.pending_moves) == 1


def test_89_2_a_player_may_transport_only_units_owned_by_them() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.CARRIER, system_id=0)
    friendly_ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    enemy_ground_force = make_unit_with_id(
        unit_id=2,
        owner_name="B",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    state = build_game_state(
        players=(player_a, player_b),
        galaxy=Galaxy(
            {
                System(id=0, command_tokens=(), coordinates=HexCoord(0, 0)),
                System(id=1, command_tokens=(), coordinates=HexCoord(1, 0)),
            },
        ),
        turn_context=TurnContext(
            has_initiated_action=True,
            tactical_action_step=TacticalActionStep.MOVEMENT,
            active_system_id=1,
        ),
        units=frozenset({ship, friendly_ground_force, enemy_ground_force}),
    )
    engine = get_default_game_engine()
    move_attempt = move_command(
        actor="A",
        ship_id=0,
        to_system_id=1,
        transported_unit_ids=frozenset(
            {friendly_ground_force.unit_id, enemy_ground_force.unit_id},
        ),
    )
    current_state = state

    for command in move_attempt:
        result = engine.apply_command(
            state=current_state,
            command=command,
        )
        if not result.success:
            return
        current_state = result.new_state

    pytest.fail("Expect enemy unit to break success criterion.")


def test_89_2_a_cannot_transport_units_not_on_path() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.CARRIER, system_id=0)
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=2,
    )
    state = replace(state, units=frozenset({ship, ground_force}))
    move_attempt = move_command(
        actor="A",
        ship_id=0,
        to_system_id=1,
        transported_unit_ids=frozenset({ground_force.unit_id}),
    )

    result = engine.apply_command(
        state=state,
        command=move_attempt[0],
    )
    assert result.success
    result = engine.apply_command(state=result.new_state, command=move_attempt[1])

    assert not result.success


def test_89_2_cannot_transport_unit_twice() -> None:
    engine = get_default_game_engine()
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.CARRIER, system_id=0)
    ship2 = make_unit_with_id(unit_id=2, owner_name="A", kind=ShipKind.CARRIER, system_id=0)
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    session = make_movement_session(units=frozenset({ship, ship2, ground_force}))
    move_attempt = move_command(
        actor="A",
        ship_id=0,
        to_system_id=1,
        transported_unit_ids=frozenset({ground_force.unit_id}),
    )
    for command in move_attempt:
        session.apply_command(command)
        assert len(session.failure_history) == 0
    move_other_ship = move_command(
        actor="A",
        ship_id=2,
        to_system_id=1,
        transported_unit_ids=frozenset({ground_force.unit_id}),
    )
    session.apply_command(
        command=move_other_ship[0],
    )
    assert len(session.failure_history) == 0
    result = engine.apply_command(
        state=session.current_state,
        command=move_other_ship[1],
    )
    assert not result.success


def test_89_2_b_active_player_may_move_no_ships() -> None:
    player_a = make_player("A")
    session = make_session(
        players=(player_a,),
        turn_context=TurnContext(
            has_initiated_action=False,
            tactical_action_step=TacticalActionStep.MOVEMENT,
            active_system_id=0,
        ),
    )

    assert session.engine.apply_command(
        state=session.current_state,
        command=action_command(player_a.name, CommandType.END_MOVEMENT),
    ).success


def test_89_2_c_players_may_use_space_cannon_after_movement() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    session = make_session(players=(player_a, player_b))

    use_space_cannon = action_command(player_b.name, CommandType.USE_SPACE_CANNON)
    assert not session.engine.apply_command(
        state=session.current_state,
        command=use_space_cannon,
    ).success

    new_state = session.apply_command(action_command(player_a.name, CommandType.END_MOVEMENT))
    result = session.engine.apply_command(state=new_state, command=use_space_cannon)

    assert result.success


def test_89_2_c_space_cannon_window_closes_after_all_players_have_acted() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    session = make_session(players=(player_a, player_b))

    new_state = session.apply_command(action_command(player_a.name, CommandType.END_MOVEMENT))
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT

    new_state = resolve_space_cannon(session, new_state)
    assert new_state.turn_context.tactical_action_step != TacticalActionStep.MOVEMENT


def test_89_2_c_one_player_cannot_space_cannon_twice_in_same_window() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    session = make_session(players=(player_a, player_b))

    new_state = session.apply_command(action_command(player_a.name, CommandType.END_MOVEMENT))
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT
    assert new_state.active_system is not None
    assert new_state.player_may_resolve_space_cannon_in_system(
        player_name=player_a.name,
        system_id=new_state.active_system.id,
    )

    use_space_cannon = action_command(player_a.name, CommandType.USE_SPACE_CANNON)
    _ = session.apply_command(use_space_cannon)
    assert len(session.failure_history) == 0
    assert not session.engine.apply_command(
        state=session.current_state,
        command=use_space_cannon,
    ).success


def test_89_2_c_players_may_choose_to_skip_space_cannon() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    session = make_session(players=(player_a, player_b))

    new_state = session.apply_command(action_command(player_a.name, CommandType.END_MOVEMENT))
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT
    assert new_state.active_system is not None
    assert new_state.player_may_resolve_space_cannon_in_system(
        player_name=player_a.name,
        system_id=new_state.active_system.id,
    )

    new_state = session.apply_command(action_command(player_a.name, CommandType.PASS_SPACE_CANNON))
    assert session.last_command_result.success
    assert new_state.window_context.player_has_passed_on_window(
        player_name=player_a.name,
        window=Window.AFTER_MOVE_SHIPS_STEP,
    )
    assert not session.engine.apply_command(
        new_state,
        action_command(player_a.name, CommandType.USE_SPACE_CANNON),
    ).success

    new_state = session.apply_command(action_command(player_b.name, CommandType.PASS_SPACE_CANNON))
    assert len(session.failure_history) == 0
    assert new_state.turn_context.tactical_action_step != TacticalActionStep.MOVEMENT


def test_89_2_c_ability_window_properly_clears_state() -> None:
    player_a = make_player("A", strategy_cards=(StrategyCard(name="LEADERSHIP", initiative=1),))
    player_b = make_player("B", strategy_cards=(StrategyCard(name="DIPLOMACY", initiative=2),))
    session = make_session(players=(player_a, player_b))

    new_state = session.apply_command(action_command(player_a.name, CommandType.END_MOVEMENT))
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT

    a_use_space_cannon = action_command(player_a.name, CommandType.USE_SPACE_CANNON)
    b_use_space_cannon = action_command(player_b.name, CommandType.USE_SPACE_CANNON)
    _ = session.apply_command(a_use_space_cannon)
    new_state = session.apply_command(b_use_space_cannon)
    _ = session.apply_command_result(
        command_result=CommandResult(
            success=True,
            new_state=new_state.close_all_windows(),
            events=[],
        ),
    )
    _ = session.apply_command(action_command(player_a.name, CommandType.END_TURN))

    new_state = session.apply_command(activate_command(actor=player_b.name, system_id=0))
    new_state = session.apply_command(action_command(player_b.name, CommandType.END_MOVEMENT))

    assert new_state.active_system is not None
    assert len(session.failure_history) == 0
    assert session.engine.apply_command(
        state=session.current_state,
        command=action_command(player_a.name, CommandType.USE_SPACE_CANNON),
    ).success


@given(
    ships=st.lists(
        st.builds(
            make_unit_with_id,
            unit_id=st.sampled_from(range(11)),
            owner_name=st.just("A"),
            kind=st.sampled_from([kind for kind in list(ShipKind) if kind != ShipKind.FIGHTER]),
            system_id=st.integers(
                min_value=min(system.id for system in CENTRE_RING_OF_SYSTEMS if system.id != 0),
                max_value=max(system.id for system in CENTRE_RING_OF_SYSTEMS if system.id != 0),
            ),
        ),
        min_size=1,
        max_size=5,
    ),
)
def test_89_move_resolves_correctly(ships: list[Unit]) -> None:
    unique_ships = grant_all_units_unique_ids(frozenset(ships))
    session = GameSession(
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=unique_ships,
            systems=CENTRE_RING_OF_SYSTEMS_WITH_PLAYER_A_TOKEN,
        ),
        engine=get_default_game_engine(),
    )

    for ship in unique_ships:
        session.apply_command(
            command=move_command(
                actor="A",
                ship_id=ship.unit_id,
                to_system_id=0,
            )[0],
        )
        if session.current_state.window_context.is_window_active(Window.TRANSPORT_UNITS):
            session.apply_command(
                command=Command(
                    "A",
                    command_type=CommandType.PASS_TRANSPORT_UNIT,
                ),
            )
        assert len(session.failure_history) == 0

    new_state = session.apply_command(
        action_command("A", CommandType.END_MOVEMENT),
    )

    for ship in unique_ships:
        new_ship = new_state.get_ship_from_id(ship.unit_id)
        assert new_state.get_current_system(new_ship) == new_state.active_system

    assert new_state.turn_context.pending_moves == frozenset()


@given(
    units=st.lists(
        st.builds(
            make_unit_with_id,
            unit_id=st.integers(min_value=0, max_value=10),
            owner_name=st.just("A"),
            kind=st.sampled_from(
                [ShipKind.FIGHTER, GroundForceKind.INFANTRY, GroundForceKind.MECH],
            ),
            system_id=st.just(0),
            planet_id=st.just(0),
        ),
        min_size=1,
        max_size=4,
    ),
)
def test_89_transport_resolves_correctly(units: list[Unit]) -> None:
    unique_units = grant_all_units_unique_ids(frozenset(units))
    ship = make_unit_with_id(
        unit_id=len(unique_units),
        owner_name="A",
        kind=ShipKind.CARRIER,
        system_id=0,
    )
    unique_units = frozenset(unique_units.union({ship}))
    session = GameSession(
        initial_state=make_tactical_action_movement_state(
            active_system_id=1,
            units=unique_units,
            systems=make_centre_ring_with_player_token("A", 1),
        ),
        engine=get_default_game_engine(),
    )

    transported_unit_ids = frozenset(
        unit.unit_id for unit in unique_units if unit.unit_id != ship.unit_id
    )
    for unit in session.current_state.units:
        if unit.is_ground_force:
            assert unit.cast_to_ground_force().planet_id is not None
    for command in move_command(
        actor="A",
        ship_id=ship.unit_id,
        to_system_id=1,
        transported_unit_ids=transported_unit_ids,
    ):
        new_state = session.apply_command(command)
    assert len(session.failure_history) == 0

    new_state = session.apply_command(
        action_command("A", CommandType.END_MOVEMENT),
    )
    for unit in unique_units:
        new_unit = new_state.get_unit_from_id(unit.unit_id)
        assert new_state.get_current_system(new_unit) == new_state.active_system
        if new_unit.is_ground_force:
            assert new_unit.cast_to_ground_force().planet_id is None

    assert new_state.turn_context.pending_moves == frozenset()


@given(opponent_has_ground_force=st.booleans())
def test_89_3_if_one_player_has_ships_skip_space_combat(*, opponent_has_ground_force: bool) -> None:
    ship_a = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DESTROYER, system_id=0)
    ground_forces = (
        {make_unit_with_id(unit_id=1, owner_name="B", kind=GroundForceKind.INFANTRY, system_id=1)}
        if opponent_has_ground_force
        else set[Unit]()
    )

    session = GameSession(
        initial_state=make_tactical_action_movement_state(
            active_system_id=1,
            units=frozenset({ship_a} | ground_forces),
            players=(make_player("A"), make_player("B")),
            systems=CENTRE_RING_OF_SYSTEMS,
        ),
        engine=get_default_game_engine(),
    )

    new_state = session.apply_command(
        command=move_command(
            actor="A",
            ship_id=0,
            to_system_id=1,
        )[0],
    )
    new_state = session.apply_command(
        command=action_command(new_state.active_player.name, CommandType.END_MOVEMENT),
    )

    assert new_state.get_ships_in_system(system_id=1) == frozenset(
        {new_state.get_ship_from_id(ship_id=0)},
    )

    for player in new_state.players:
        new_state = session.apply_command(
            command=action_command(player.name, CommandType.USE_SPACE_CANNON),
        )

    assert new_state.turn_context.tactical_action_step != TacticalActionStep.SPACE_COMBAT


def test_89_3_if_two_players_have_ships_they_must_resolve_space_combat() -> None:
    ship_a = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DESTROYER, system_id=0)
    ship_b = make_unit_with_id(unit_id=1, owner_name="B", kind=ShipKind.DESTROYER, system_id=1)

    session = GameSession(
        initial_state=make_tactical_action_movement_state(
            active_system_id=1,
            units=frozenset({ship_a, ship_b}),
            players=(make_player("A"), make_player("B")),
            systems=CENTRE_RING_OF_SYSTEMS,
        ),
        engine=get_default_game_engine(),
    )

    new_state = session.apply_command(
        command=move_command(
            actor="A",
            ship_id=0,
            to_system_id=1,
        )[0],
    )
    new_state = session.apply_command(
        command=action_command(new_state.active_player.name, CommandType.END_MOVEMENT),
    )

    assert (
        new_state.get_ship_from_id(ship_id=0).system_id
        == new_state.get_ship_from_id(ship_id=1).system_id
    )

    for player in new_state.players:
        new_state = session.apply_command(
            command=action_command(player.name, CommandType.USE_SPACE_CANNON),
        )

    assert new_state.turn_context.tactical_action_step == TacticalActionStep.SPACE_COMBAT


def test_89_4_active_player_may_use_their_bombardment_during_invasion() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=0)
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="B",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    session = make_session(
        players=(player_a, player_b),
        galaxy=Galaxy({System(id=0, command_tokens=())}),
        units=frozenset({ship, ground_force}),
    )

    new_state = end_movement(session, session.current_state)
    for player in new_state.players:
        new_state = session.apply_command(
            command=action_command(player.name, CommandType.USE_SPACE_CANNON),
        )

    assert new_state.turn_context.tactical_action_step == TacticalActionStep.INVASION
    assert session.engine.apply_command(
        state=session.current_state,
        command=action_command(player_a.name, CommandType.USE_BOMBARDMENT),
    ).success
    assert not session.engine.apply_command(
        state=session.current_state,
        command=action_command(player_b.name, CommandType.USE_BOMBARDMENT),
    ).success


def test_89_4_player_may_skip_bombardment() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=0)
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="B",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    session = make_session(
        players=(player_a, player_b),
        galaxy=Galaxy({System(id=0, command_tokens=())}),
        units=frozenset({ship, ground_force}),
    )

    new_state = begin_invasion(session, session.current_state)
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.INVASION

    new_state = session.apply_command(action_command(player_a.name, CommandType.PASS_BOMBARDMENT))
    assert session.last_command_result.success
    assert Window.TACTICAL_ACTION_BOMBARDMENT not in new_state.window_context.active_windows


def test_89_4_player_may_commit_ground_forces() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=0)
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    session = make_session(
        players=(player_a, player_b),
        galaxy=Galaxy({System(id=0, command_tokens=(), planets=frozenset({Planet(0)}))}),
        units=frozenset({ship, ground_force}),
    )

    invaded_state = begin_invasion(session, session.current_state)
    assert invaded_state.turn_context.tactical_action_step == TacticalActionStep.INVASION

    invaded_state = session.apply_command(
        action_command(player_a.name, CommandType.PASS_BOMBARDMENT),
    )
    assert session.last_command_result.success

    invaded_state = session.apply_command(
        command=CommitGroundForceCommand(
            actor="A",
            command_type=CommandType.COMMIT_GROUND_FORCE,
            ground_force_id=ground_force.unit_id,
            to_planet_id=0,
        ),
    )
    invaded_state = session.apply_command(
        command=action_command("A", CommandType.END_INVASION),
    )

    ground_force_after_commit = invaded_state.get_ground_force_from_id(ground_force.unit_id)
    assert ground_force_after_commit.system_id == 0
    assert ground_force_after_commit.planet_id == 0


def test_89_4_player_cannot_commit_if_not_in_active_system() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=0)
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=1,
    )
    session = make_session(
        players=(player_a, player_b),
        galaxy=Galaxy(
            {
                System(id=0, command_tokens=(), planets=frozenset({Planet(0)})),
                System(id=1, command_tokens=(), planets=frozenset({Planet(1)})),
            },
        ),
        units=frozenset({ship, ground_force}),
    )

    invaded_state = begin_invasion(session, session.current_state)
    assert invaded_state.turn_context.tactical_action_step == TacticalActionStep.INVASION

    invaded_state = session.apply_command(
        action_command(player_a.name, CommandType.PASS_BOMBARDMENT),
    )
    assert session.last_command_result.success

    assert not session.engine.apply_command(
        state=session.current_state,
        command=CommitGroundForceCommand(
            actor="A",
            command_type=CommandType.COMMIT_GROUND_FORCE,
            ground_force_id=ground_force.unit_id,
            to_planet_id=0,
        ),
    ).success


def test_89_4_player_cannot_commit_other_players_ground_force() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=0)
    ground_force_a = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    ground_force_b = make_unit_with_id(
        unit_id=2,
        owner_name="B",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    session = make_session(
        players=(player_a, player_b),
        galaxy=Galaxy({System(id=0, command_tokens=())}),
        units=frozenset({ship, ground_force_a, ground_force_b}),
    )

    _ = begin_invasion(session, session.current_state)
    commit_state = pass_bombardment_window(session, session.current_state)
    assert commit_state.turn_context.tactical_action_step == TacticalActionStep.INVASION

    for bad_command in (
        CommitGroundForceCommand(
            actor="A",
            command_type=CommandType.COMMIT_GROUND_FORCE,
            ground_force_id=ground_force_b.unit_id,
            to_planet_id=0,
        ),
        CommitGroundForceCommand(
            actor="B",
            command_type=CommandType.COMMIT_GROUND_FORCE,
            ground_force_id=ground_force_a.unit_id,
            to_planet_id=0,
        ),
        CommitGroundForceCommand(
            actor="B",
            command_type=CommandType.COMMIT_GROUND_FORCE,
            ground_force_id=ground_force_b.unit_id,
            to_planet_id=0,
        ),
    ):
        result = session.engine.apply_command(state=session.current_state, command=bad_command)
        assert not result.success


def test_89_5_player_may_resolve_production_abilities() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    session = make_session(players=(player_a, player_b))
    _ = begin_invasion(session, session.current_state)
    _ = pass_bombardment_window(session, session.current_state)
    premature_production = action_command(player_a.name, CommandType.USE_PRODUCTION)
    assert not session.engine.apply_command(
        state=session.current_state,
        command=premature_production,
    ).success
    invaded_state = session.apply_command(
        command=action_command("A", CommandType.END_INVASION),
    )
    assert invaded_state.turn_context.tactical_action_step == TacticalActionStep.PRODUCTION
    legal_commands = [
        Command(actor=player_a.name, command_type=CommandType.USE_PRODUCTION),
        Command(actor=player_a.name, command_type=CommandType.PASS_PRODUCTION),
    ]
    illegal_commands = [
        Command(actor=player_b.name, command_type=CommandType.USE_PRODUCTION),
        Command(actor=player_b.name, command_type=CommandType.PASS_PRODUCTION),
    ]
    for legal_command in legal_commands:
        result = session.engine.apply_command(state=session.current_state, command=legal_command)
        assert result.success
    for illegal_command in illegal_commands:
        result = session.engine.apply_command(state=session.current_state, command=illegal_command)
        assert not result.success


def test_89_after_production_game_context_is_clear() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    session = make_session(players=(player_a, player_b))
    _ = begin_invasion(session, session.current_state)
    _ = pass_bombardment_window(session, session.current_state)
    _ = session.apply_command(
        command=action_command("A", CommandType.END_INVASION),
    )
    end_production_state = session.apply_command(
        command=action_command("A", CommandType.PASS_PRODUCTION),
    )
    assert end_production_state.turn_context.tactical_action_step is None
    assert session.engine.apply_command(
        state=end_production_state,
        command=Command(actor=player_a.name, command_type=CommandType.END_TURN),
    ).success
    assert not session.engine.apply_command(
        state=end_production_state,
        command=Command(actor=player_b.name, command_type=CommandType.END_TURN),
    ).success


def test_no_ships_with_move_in_retreat_step_is_legal() -> None:
    player_a = make_player(
        "A",
        command_sheet=CommandSheet.make_from_int(
            player_name="A",
            tactic=2,
            fleet=3,
            strategy=2,
            reinforcements=8,
        ),
    )
    player_b = make_player("B")
    ships = {
        make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.FIGHTER, system_id=0),
        make_unit_with_id(unit_id=1, owner_name="B", kind=ShipKind.DESTROYER, system_id=0),
    }

    session = make_session(
        players=(player_a, player_b),
        active_player=player_a,
        turn_context=TurnContext(
            has_initiated_action=True,
            tactical_action_step=TacticalActionStep.SPACE_COMBAT,
            space_combat_context=SpaceCombatContext(
                step=SpaceCombatStep.RETREAT,
                round_number=1,
                attacker="A",
                defender="B",
                retreat_declaration=RetreatDeclaration(
                    attacker_has_declared=True,
                    defender_has_declared=False,
                ),
            ),
            active_system_id=0,
            pending_moves=frozenset(),
        ),
        galaxy=CENTRE_RING_OF_SYSTEMS_WITH_PLAYER_A_TOKEN,
        units=frozenset(ships),
    )

    result = session.engine.apply_command(
        state=session.current_state,
        command=action_command(player_a.name, CommandType.END_RETREAT),
    )

    assert result.success
