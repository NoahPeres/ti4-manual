from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from src.engine.actions.movement import MoveShipCommand
from src.engine.actions.tactical_action import ActivateCommand
from src.engine.core.command import Command, CommandType
from src.engine.core.game_engine import CommandResult
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import (
    Ability,
    GameState,
    HexCoord,
    Phase,
    System,
    TacticalActionStep,
    TurnContext,
    Window,
)
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
        id=0,
        command_tokens=(CommandToken(player_name=player_a.name),),
    )
    previously_activated_by_b = System(
        id=0,
        command_tokens=(CommandToken(player_name=player_b.name),),
    )
    session = make_basic_session_from_players(players=(player_a, player_b))
    assert session.engine.apply_command(
        state=replace(session.current_state, galaxy=frozenset({fresh_system})),
        command=ActivateCommand(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
        ),
    ).success
    assert not session.engine.apply_command(
        state=replace(session.current_state, galaxy=frozenset({previously_activated_system})),
        command=ActivateCommand(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
        ),
    ).success
    assert session.engine.apply_command(
        state=replace(session.current_state, galaxy=frozenset({previously_activated_by_b})),
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
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
        ),
    )
    activated_system = new_state.get_system(system_id=0)
    assert any(token.player_name == player_a.name for token in activated_system.command_tokens)


def test_89_1_a_that_system_is_the_active_system() -> None:
    player_a = make_player("A")
    session = make_basic_session_from_players(players=(player_a,))
    new_state = session.apply_command(
        command=ActivateCommand(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
        ),
    )
    assert new_state.turn_context.active_system_id == 0


def test_89_1_b_other_players_tokens_do_not_prevent_activation() -> None:
    player_a = make_player("A")
    player_b = make_player("B")
    system_with_b_token = System(id=0, command_tokens=(CommandToken(player_name=player_b.name),))
    session = make_basic_session_from_players(players=(player_a, player_b))
    assert session.engine.apply_command(
        state=replace(session.current_state, galaxy=frozenset({system_with_b_token})),
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
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
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
                },
            ),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
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
                },
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
                },
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
        transported_unit_kind,
        GroundForceKind,
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

    result = engine.apply_command(
        state=state,
        command=MoveShipCommand(
            actor=state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
            transported_unit_ids=frozenset(
                {friendly_ground_force.unit_id, enemy_ground_force.unit_id},
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
        state=session.current_state,
        command=use_space_cannon,
    ).success
    new_state = session.apply_command(
        Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
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
        Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT

    for player in new_state.players:
        assert new_state.active_system is not None
        if new_state.player_may_resolve_space_cannon_in_system(
            player=player,
            system_id=new_state.active_system.id,
        ):
            new_state = session.apply_command(
                Command(actor=player, command_type=CommandType.USE_SPACE_CANNON),
            )
    assert new_state.turn_context.tactical_action_step != TacticalActionStep.MOVEMENT


def test_89_2_c_one_player_cannot_space_cannon_twice_in_same_window() -> None:
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
        Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT

    assert new_state.active_system is not None
    assert new_state.player_may_resolve_space_cannon_in_system(
        player=player_a,
        system_id=new_state.active_system.id,
    )
    use_space_cannon = Command(actor=player_a, command_type=CommandType.USE_SPACE_CANNON)
    new_state = session.apply_command(use_space_cannon)
    assert len(session.failure_history) == 0
    assert not session.engine.apply_command(
        state=session.current_state,
        command=use_space_cannon,
    ).success


def test_89_2_c_players_may_choose_to_skip_space_cannon() -> None:
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
        Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT

    assert new_state.active_system is not None
    assert new_state.player_may_resolve_space_cannon_in_system(
        player=player_a,
        system_id=new_state.active_system.id,
    )
    skip_space_cannon = Command(actor=player_a, command_type=CommandType.PASS_SPACE_CANNON)
    new_state = session.apply_command(skip_space_cannon)
    assert session.last_command_result.success
    assert (
        Ability.SPACE_CANNON
        not in new_state.window_context.get_or_create_ability_tracker(
            player=player_a,
        ).abilities_used
    )
    new_state = session.apply_command(
        Command(actor=player_b, command_type=CommandType.PASS_SPACE_CANNON),
    )
    assert len(session.failure_history) == 0
    assert new_state.turn_context.tactical_action_step != TacticalActionStep.MOVEMENT


def test_89_2_c_ability_window_properly_clears_state() -> None:
    player_a = make_player("A", strategy_cards=(StrategyCard(name="LEADERSHIP", initiative=1),))
    player_b = make_player("B", strategy_cards=(StrategyCard(name="DIPLOMACY", initiative=2),))

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
        Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT

    assert new_state.active_system is not None
    a_use_space_cannon = Command(actor=player_a, command_type=CommandType.USE_SPACE_CANNON)
    b_use_space_cannon = Command(actor=player_b, command_type=CommandType.USE_SPACE_CANNON)
    _ = session.apply_command(a_use_space_cannon)
    new_state = session.apply_command(b_use_space_cannon)
    _ = session.apply_command_result(
        command_result=CommandResult(
            success=True,
            new_state=new_state.close_all_windows(),
            events=[],
        ),
    )
    _ = session.apply_command(Command(actor=player_a, command_type=CommandType.END_TURN))

    # B's turn
    new_state = session.apply_command(
        ActivateCommand(
            actor=player_b,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
        ),
    )
    new_state = session.apply_command(
        Command(actor=player_b, command_type=CommandType.END_MOVEMENT),
    )

    assert new_state.active_system is not None
    assert len(session.failure_history) == 0
    assert session.engine.apply_command(
        state=session.current_state,
        command=Command(actor=player_a, command_type=CommandType.USE_SPACE_CANNON),
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
            systems=CENTRE_RING_OF_SYSTEMS,
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
        Command(actor=session.initial_state.get_player("A"), command_type=CommandType.END_MOVEMENT),
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
            systems=CENTRE_RING_OF_SYSTEMS,
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
        Command(actor=session.initial_state.get_player("A"), command_type=CommandType.END_MOVEMENT),
    )
    for unit in unique_units:
        new_unit = new_state.get_unit_from_id(unit.unit_id)
        assert new_state.get_current_system(new_unit) == new_state.active_system
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
            player_names=["A", "B"],
            systems=CENTRE_RING_OF_SYSTEMS,
        ),
        engine=get_default_game_engine(),
    )

    new_state = session.apply_command(
        command=MoveShipCommand(
            actor=session.current_state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
        ),
    )
    new_state = session.apply_command(
        command=Command(actor=new_state.active_player, command_type=CommandType.END_MOVEMENT),
    )

    assert new_state.get_ships_in_system(system_id=1) == frozenset(
        {new_state.get_ship_from_id(ship_id=0)},
    )

    for player in new_state.players:
        new_state = session.apply_command(
            command=Command(actor=player, command_type=CommandType.USE_SPACE_CANNON),
        )

    assert new_state.turn_context.tactical_action_step != TacticalActionStep.SPACE_COMBAT


def test_89_3_if_two_players_have_ships_they_must_resolve_space_combat() -> None:
    ship_a = make_unit_with_id(unit_id=0, owner_name="A", kind=ShipKind.DESTROYER, system_id=0)
    ship_b = make_unit_with_id(unit_id=1, owner_name="B", kind=ShipKind.DESTROYER, system_id=1)

    session = GameSession(
        initial_state=make_tactical_action_movement_state(
            active_system_id=1,
            units=frozenset({ship_a, ship_b}),
            player_names=["A", "B"],
            systems=CENTRE_RING_OF_SYSTEMS,
        ),
        engine=get_default_game_engine(),
    )

    new_state = session.apply_command(
        command=MoveShipCommand(
            actor=session.current_state.get_player("A"),
            command_type=CommandType.MOVE_SHIP,
            ship_id=0,
            to_system_id=1,
        ),
    )
    new_state = session.apply_command(
        command=Command(actor=new_state.active_player, command_type=CommandType.END_MOVEMENT),
    )

    assert (
        new_state.get_ship_from_id(ship_id=0).system_id
        == new_state.get_ship_from_id(ship_id=1).system_id
    )

    for player in new_state.players:
        new_state = session.apply_command(
            command=Command(actor=player, command_type=CommandType.USE_SPACE_CANNON),
        )

    # NOTE: actual resolution will be deferred and tested later, this is showing that it's properly
    # orchestrated only.
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
    session = GameSession(
        initial_state=GameState(
            players=(player_a, player_b),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset({System(id=0, command_tokens=())}),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
            units=frozenset({ship, ground_force}),
        ),
        engine=get_default_game_engine(),
    )
    new_state = session.apply_command(
        command=Command(
            actor=session.current_state.get_player("A"),
            command_type=CommandType.END_MOVEMENT,
        ),
    )
    for player in new_state.players:
        new_state = session.apply_command(
            command=Command(actor=player, command_type=CommandType.USE_SPACE_CANNON),
        )
    assert (
        new_state.turn_context.tactical_action_step == TacticalActionStep.INVASION
    )  # No enemy ships, so should advance to invasion immediately.

    assert session.engine.apply_command(
        state=session.current_state,
        command=Command(
            actor=session.current_state.get_player("A"),
            command_type=CommandType.USE_BOMBARDMENT,
        ),
    ).success

    assert not session.engine.apply_command(
        state=session.current_state,
        command=Command(
            actor=session.current_state.get_player("B"),
            command_type=CommandType.USE_BOMBARDMENT,
        ),
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
    session = GameSession(
        initial_state=GameState(
            players=(player_a, player_b),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset({System(id=0, command_tokens=())}),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
            units=frozenset({ship, ground_force}),
        ),
        engine=get_default_game_engine(),
    )
    new_state = session.apply_command(
        command=Command(
            actor=session.current_state.get_player("A"),
            command_type=CommandType.END_MOVEMENT,
        ),
    )
    for player in new_state.players:
        new_state = session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_SPACE_CANNON),
        )
    assert (
        new_state.turn_context.tactical_action_step == TacticalActionStep.INVASION
    )  # No enemy ships, so should advance to invasion immediately.

    new_state = session.apply_command(
        Command(
            actor=session.current_state.get_player("A"),
            command_type=CommandType.PASS_BOMBARDMENT,
        ),
    )
    assert session.last_command_result.success
    assert Window.TACTICAL_ACTION_BOMBARDMENT not in new_state.window_context.active_windows
