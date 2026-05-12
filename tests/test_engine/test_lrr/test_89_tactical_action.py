from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from src.engine.actions.movement import MoveShipCommand
from src.engine.actions.tactical_action import ActivateCommand
from src.engine.core.command import Command, CommandType
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import (
    GameState,
    HexCoord,
    Phase,
    System,
    TacticalActionStep,
    TurnContext,
)
from src.engine.tokens import CommandToken
from src.engine.units.units import (
    GroundForceKind,
    ShipKind,
    Unit,
    UnitKind,
    make_unit_with_id,
)
from tests.test_engine.test_lrr.common import (
    get_default_game_engine,
    grant_all_units_unique_ids,
    make_basic_session_from_players,
    make_player,
    make_tactical_action_movement_state,
)


def test_89_1_active_player_must_activate_system_without_their_command_token() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    fresh_system = System(id=0, command_tokens=())
    previously_activated_system = System(
        id=0, command_tokens=(CommandToken(player_name=player_a.name),)
    )
    previously_activated_by_b = System(
        id=0, command_tokens=(CommandToken(player_name=player_b.name),)
    )
    session = make_basic_session_from_players(players=(player_a, player_b))
    assert session.engine.apply_command(
        state=replace(session.current_state, galaxy={fresh_system}),
        command=ActivateCommand(
            actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION, system_id=0
        ),
    ).success
    assert not session.engine.apply_command(
        state=replace(session.current_state, galaxy={previously_activated_system}),
        command=ActivateCommand(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
        ),
    ).success
    assert session.engine.apply_command(
        state=replace(session.current_state, galaxy={previously_activated_by_b}),
        command=ActivateCommand(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
        ),
    ).success


def test_89_1_a_active_player_places_token_from_tactic_pool() -> None:
    player_a = make_player("A")
    session = make_basic_session_from_players(players=(player_a,))
    new_state = session.apply_command(
        command=ActivateCommand(
            actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION, system_id=0
        ),
    )
    activated_system = new_state.get_system(system_id=0)
    assert any(token.player_name == player_a.name for token in activated_system.command_tokens)


def test_89_1_a_that_system_is_the_active_system() -> None:
    player_a = make_player("A")
    session = make_basic_session_from_players(players=(player_a,))
    new_state = session.apply_command(
        command=ActivateCommand(
            actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION, system_id=0
        ),
    )
    assert new_state.turn_context.active_system_id == 0


def test_89_1_b_other_players_tokens_do_not_prevent_activation() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    system_with_b_token = System(id=0, command_tokens=(CommandToken(player_name=player_b.name),))
    session = make_basic_session_from_players(players=(player_a, player_b))
    assert session.engine.apply_command(
        state=replace(session.current_state, galaxy={system_with_b_token}),
        command=ActivateCommand(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
        ),
    ).success


def test_89_1_advance_to_movement_after_activation() -> None:
    player_a = make_player("A")
    session = make_basic_session_from_players(players=(player_a,))
    new_state = session.apply_command(
        command=ActivateCommand(
            actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION, system_id=0
        ),
    )
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT


def test_89_2_only_active_player_moves_ships() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    session = GameSession(
        initial_state=GameState(
            players=(player_a, player_b),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset(
                {
                    System(id=0, command_tokens=()),
                    System(
                        id=1,
                        command_tokens=(),
                    ),
                }
            ),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
            units=frozenset(
                {
                    make_unit_with_id(
                        unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=0
                    )
                }
            ),
        ),
        engine=get_default_game_engine(),
    )
    result = session.engine.apply_command(
        state=session.current_state,
        command=MoveShipCommand(
            actor=player_b,
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=0,
        ),
    )
    assert not result.success


def test_89_2_active_player_may_move_only_their_ships() -> None:
    ship = make_unit_with_id(unit_id=0, owner_name="B", kind=ShipKind.DREADNOUGHT, system_id=1)
    player_a = make_player("A")
    player_b = make_player("B")
    session = GameSession(
        initial_state=GameState(
            players=(player_a, player_b),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset(
                {
                    System(id=0, command_tokens=()),
                    System(id=1, command_tokens=()),
                }
            ),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
            units=frozenset({ship}),
        ),
        engine=get_default_game_engine(),
    )
    active_system = session.current_state.active_system

    assert active_system is not None
    result = session.engine.apply_command(
        state=session.current_state,
        command=MoveShipCommand(
            actor=player_a,
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=active_system.id,
        ),
    )
    assert not result.success


def test_89_2_may_not_move_ships_from_systems_with_command_tokens() -> None:
    ship = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DREADNOUGHT, system_id=1)
    player_a = make_player("A")
    session = GameSession(
        initial_state=GameState(
            players=(player_a,),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset(
                {
                    System(id=0, command_tokens=()),
                    System(
                        id=1,
                        command_tokens=(CommandToken(player_name="A"),),
                    ),
                }
            ),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
            units=frozenset({ship}),
        ),
        engine=get_default_game_engine(),
    )
    active_system = session.current_state.active_system

    assert active_system is not None
    result = session.engine.apply_command(
        state=session.current_state,
        command=MoveShipCommand(
            actor=player_a,
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=active_system.id,
        ),
    )
    assert not result.success


def test_89_2_ships_with_insufficient_move_cannot_move() -> None:
    state = make_tactical_action_movement_state(active_system_id=2)
    engine = get_default_game_engine()

    result = engine.apply_command(
        state=state,
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=2,
        ),
    )
    assert not result.success
    assert len(result.new_state.turn_context.pending_moves) == 0


def test_89_2_ship_with_sufficient_move_may_move() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()
    result = engine.apply_command(
        state=state,
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
        ),
    )
    assert result.success
    assert len(result.new_state.turn_context.pending_moves) == 1


def test_89_2_move_into_active_system() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()
    result = engine.apply_command(
        state=state,
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
        ),
    )
    move = next(iter(result.new_state.turn_context.pending_moves))
    assert move.to_system_id == 1


def test_89_2_cannot_move_into_non_active_system() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()
    result = engine.apply_command(
        state=state,
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=2,
        ),
    )
    assert not result.success
    assert len(result.new_state.turn_context.pending_moves) == 0


def test_89_2_a_ships_with_capacity_can_transport_other_units() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()
    ship = make_unit_with_id(
        unit_id=0,
        owner_name="A",
        kind=ShipKind.DREADNOUGHT,
        system_id=0,
    )
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    result = engine.apply_command(
        state=replace(state, units=frozenset({ship, ground_force})),
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
            transported_unit_ids=frozenset({ground_force.unit_id}),
        ),
    )
    assert result.success
    assert len(result.new_state.turn_context.pending_moves) == 1
    (move,) = result.new_state.turn_context.pending_moves
    assert len(move.transported_unit_ids) == 1


def test_89_2_a_ships_with_no_capacity_cannot_transport_other_units() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()
    ship = make_unit_with_id(
        unit_id=0,
        owner_name="A",
        kind=ShipKind.DESTROYER,
        system_id=0,
    )
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=0,
    )
    result = engine.apply_command(
        state=replace(state, units=frozenset({ship, ground_force})),
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
            transported_unit_ids=frozenset({ground_force.unit_id}),
        ),
    )
    assert not result.success
    assert len(result.new_state.turn_context.pending_moves) == 0


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
    fighter = make_unit_with_id(
        unit_id=2,
        owner_name="A",
        kind=ShipKind.FIGHTER,
        system_id=0,
    )
    result = engine.apply_command(
        state=replace(state, units=frozenset({ship, ground_force, fighter})),
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
            transported_unit_ids=frozenset({ground_force.unit_id, fighter.unit_id}),
        ),
    )
    assert not result.success
    assert len(result.new_state.turn_context.pending_moves) == 0


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
    result = engine.apply_command(
        state=replace(state, units=frozenset({ship, transported_unit})),
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
            transported_unit_ids=frozenset({transported_unit.unit_id}),
        ),
    )
    if transported_unit_kind == ShipKind.FIGHTER or isinstance(
        transported_unit_kind, GroundForceKind
    ):
        assert result.success
        assert len(result.new_state.turn_context.pending_moves) == 1
        (move,) = result.new_state.turn_context.pending_moves
        assert len(move.transported_unit_ids) == 1
    else:
        assert not result.success
        assert len(result.new_state.turn_context.pending_moves) == 0


def test_89_2_a_player_may_transport_no_units() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()
    ship = make_unit_with_id(
        unit_id=0,
        owner_name="A",
        kind=ShipKind.DESTROYER,
        system_id=0,
    )
    result = engine.apply_command(
        state=replace(state, units=frozenset({ship})),
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
            transported_unit_ids=frozenset(),
        ),
    )
    assert result.success
    assert len(result.new_state.turn_context.pending_moves) == 1
    assert (
        len(next(move for move in result.new_state.turn_context.pending_moves).transported_unit_ids)
        == 0
    )


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
    state = GameState(
        players=(player_a, player_b),
        active_player=player_a,
        phase=Phase.ACTION,
        galaxy=frozenset(
            {
                System(id=0, command_tokens=(), coordinates=HexCoord(0, 0)),
                System(id=1, command_tokens=(), coordinates=HexCoord(1, 0)),
            }
        ),
        turn_context=TurnContext(
            has_initiated_action=True,
            tactical_action_step=TacticalActionStep.MOVEMENT,
            active_system_id=1,
        ),
        units=frozenset({ship, friendly_ground_force, enemy_ground_force}),
    )
    engine = get_default_game_engine()

    result = engine.apply_command(
        state=state,
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
            transported_unit_ids=frozenset(
                {friendly_ground_force.unit_id, enemy_ground_force.unit_id}
            ),
        ),
    )
    assert not result.success
    assert len(result.new_state.turn_context.pending_moves) == 0


def test_89_2_a_cannot_transport_units_not_on_path() -> None:
    state = make_tactical_action_movement_state(active_system_id=1)
    engine = get_default_game_engine()
    ship = make_unit_with_id(
        unit_id=0,
        owner_name="A",
        kind=ShipKind.CARRIER,
        system_id=0,
    )
    ground_force = make_unit_with_id(
        unit_id=1,
        owner_name="A",
        kind=GroundForceKind.INFANTRY,
        system_id=2,
    )
    result = engine.apply_command(
        state=replace(state, units=frozenset({ship, ground_force})),
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
            transported_unit_ids=frozenset({ground_force.unit_id}),
        ),
    )
    assert not result.success
    assert len(result.new_state.turn_context.pending_moves) == 0


def test_89_2_b_active_player_may_move_no_ships() -> None:
    player_a = make_player("A")
    session = GameSession(
        initial_state=GameState(
            players=(player_a,),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset({System(id=0, command_tokens=()), System(id=1, command_tokens=())}),
            turn_context=TurnContext(
                has_initiated_action=False,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
        ),
        engine=get_default_game_engine(),
    )
    assert session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    ).success


def test_89_2_c_players_may_use_space_cannon_after_movement() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    session = GameSession(
        initial_state=GameState(
            players=(player_a, player_b),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset({System(id=0, command_tokens=()), System(id=1, command_tokens=())}),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
        ),
        engine=get_default_game_engine(),
    )
    use_space_cannon = Command(actor=player_b, command_type=CommandType.USE_SPACE_CANNON)
    assert not session.engine.apply_command(
        state=session.current_state, command=use_space_cannon
    ).success
    new_state = session.apply_command(
        Command(actor=player_a, command_type=CommandType.END_MOVEMENT)
    )
    result = session.engine.apply_command(state=new_state, command=use_space_cannon)
    assert result.success


def test_89_2_c_space_cannon_window_closes_after_all_players_have_acted() -> None:
    player_a = make_player("A")
    player_b = make_player("B")

    session = GameSession(
        initial_state=GameState(
            players=(player_a, player_b),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset({System(id=0, command_tokens=()), System(id=1, command_tokens=())}),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
        ),
        engine=get_default_game_engine(),
    )
    new_state = session.apply_command(
        Command(actor=player_a, command_type=CommandType.END_MOVEMENT)
    )
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT

    for player in new_state.players:
        assert new_state.active_system is not None
        if new_state.player_may_resolve_space_cannon_in_system(
            player=player, system_id=new_state.active_system.id
        ):
            new_state = session.apply_command(
                Command(actor=player, command_type=CommandType.USE_SPACE_CANNON)
            )
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.SPACE_COMBAT


def test_89_2_c_one_player_cannot_space_cannon_twice() -> None:
    player_a = make_player("A")
    player_b = make_player("B")

    session = GameSession(
        initial_state=GameState(
            players=(player_a, player_b),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset({System(id=0, command_tokens=()), System(id=1, command_tokens=())}),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
        ),
        engine=get_default_game_engine(),
    )
    new_state = session.apply_command(
        Command(actor=player_a, command_type=CommandType.END_MOVEMENT)
    )
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT

    assert new_state.active_system is not None
    assert new_state.player_may_resolve_space_cannon_in_system(
        player=player_a, system_id=new_state.active_system.id
    )
    use_space_cannon = Command(actor=player_a, command_type=CommandType.USE_SPACE_CANNON)
    new_state = session.apply_command(use_space_cannon)
    assert len(session.failure_history) == 0
    assert not session.engine.apply_command(
        state=session.current_state, command=use_space_cannon
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
    }
)


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
            active_system_id=0, units=unique_ships, systems=CENTRE_RING_OF_SYSTEMS
        ),
        engine=get_default_game_engine(),
    )
    move_commands = [
        MoveShipCommand(
            actor=session.initial_state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=ship.unit_id,
            to_system_id=0,
        )
        for ship in unique_ships
    ]
    for command in move_commands:
        new_state = session.apply_command(command)
        assert len(session.failure_history) == 0
    new_state = session.apply_command(
        Command(actor=session.initial_state.get_player("A"), command_type=CommandType.END_MOVEMENT)
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
                [ShipKind.FIGHTER, GroundForceKind.INFANTRY, GroundForceKind.MECH]
            ),
            system_id=st.just(0),
        ),
        min_size=1,
        max_size=4,
    )
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
            active_system_id=1, units=unique_units, systems=CENTRE_RING_OF_SYSTEMS
        ),
        engine=get_default_game_engine(),
    )
    transported_unit_ids = frozenset(
        unit.unit_id for unit in unique_units if unit.unit_id != ship.unit_id
    )
    move_command = MoveShipCommand(
        actor=session.initial_state.get_player("A"),
        command_type=CommandType.MOVE_SHIP,
        ship_id=ship.unit_id,
        to_system_id=1,
        transported_unit_ids=transported_unit_ids,
    )
    new_state = session.apply_command(move_command)
    assert len(session.failure_history) == 0
    new_state = session.apply_command(
        Command(actor=session.initial_state.get_player("A"), command_type=CommandType.END_MOVEMENT)
    )
    for unit in unique_units:
        new_unit = new_state.get_unit_from_id(unit.unit_id)
        assert new_state.get_current_system(new_unit) == new_state.active_system
    assert new_state.turn_context.pending_moves == frozenset()


"""STEP 2—MOVEMENT: The active player may move any
number of ships that have a sufficient move value from any
number of systems that do not contain one of their command
tokens into the active system, following the rules for
movement.
a Ships that have capacity values can transport ground forces
and fighters when moving.
b The player may choose to not move any ships.
c After the “Move Ships” step, all players can use the “Space
Cannon” abilities of their units in the active system.

- Active player may move ships
- May move any number of ships
- Every ship must have sufficient move value
- Ships may only move from systems that do not contain command tokens
- Ships move into the active system

- Ships that have capacity can transport ground forces and fighters
- Player may choose to not move any ships
- After move ships step, all players can use space cannon abilities of units in active system
"""
