from dataclasses import replace

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
from src.engine.core.player import CommandSheet, Player
from src.engine.strategy_cards import StrategyCard
from src.engine.tokens import CommandToken
from src.engine.units.ships import Ship, ShipKind, ShipStats
from tests.test_engine.test_lrr.common import (
    get_default_game_engine,
    make_basic_session_from_players,
)


def test_89_1_active_player_must_activate_system_without_their_command_token() -> None:
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=0, strategy=0),
    )
    player_b = Player(
        name="B",
        strategy_cards=(StrategyCard(name="Diplomacy", initiative=2),),
        command_sheet=CommandSheet.make_from_int("B", tactic=1, fleet=0, strategy=0),
    )
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
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=0, strategy=0),
    )
    session = make_basic_session_from_players(players=(player_a,))
    new_state = session.apply_command(
        command=ActivateCommand(
            actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION, system_id=0
        ),
    )
    activated_system = new_state.get_system(id=0)
    assert any(token.player_name == player_a.name for token in activated_system.command_tokens)


def test_89_1_a_that_system_is_the_active_system() -> None:
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=0, strategy=0),
    )
    session = make_basic_session_from_players(players=(player_a,))
    new_state = session.apply_command(
        command=ActivateCommand(
            actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION, system_id=0
        ),
    )
    assert new_state.turn_context.active_system_id == 0


def test_89_1_b_other_players_tokens_do_not_prevent_activation() -> None:
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=0, strategy=0),
    )
    player_b = Player(
        name="B",
        strategy_cards=(StrategyCard(name="Diplomacy", initiative=2),),
        command_sheet=CommandSheet.make_from_int("B", tactic=1, fleet=0, strategy=0),
    )
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
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=0, strategy=0),
    )
    session = make_basic_session_from_players(players=(player_a,))
    new_state = session.apply_command(
        command=ActivateCommand(
            actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION, system_id=0
        ),
    )
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT


def test_89_2_only_active_player_moves_ships() -> None:
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=3, strategy=0),
    )
    player_b = Player(
        name="B",
        strategy_cards=(StrategyCard(name="Diplomacy", initiative=2),),
        command_sheet=CommandSheet.make_from_int("B", tactic=1, fleet=3, strategy=0),
    )
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
                        ships=frozenset(
                            {Ship(ship_id=0, owner_name=player_b.name, kind=ShipKind.DREADNOUGHT)}
                        ),
                    ),
                }
            ),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
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
    ship = Ship(kind=ShipKind.DREADNOUGHT, owner_name="B", ship_id=0)
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=3, strategy=0),
    )
    player_b = Player(
        name="B",
        strategy_cards=(StrategyCard(name="Diplomacy", initiative=2),),
        command_sheet=CommandSheet.make_from_int("B", tactic=1, fleet=3, strategy=0),
    )
    session = GameSession(
        initial_state=GameState(
            players=(player_a, player_b),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset(
                {
                    System(id=0, command_tokens=()),
                    System(id=1, command_tokens=(), ships=frozenset({ship})),
                }
            ),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
            ships=frozenset({ship}),
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
    ship = Ship(kind=ShipKind.DREADNOUGHT, owner_name="A", ship_id=0)
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=3, strategy=0),
    )
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
                        ships=frozenset({ship}),
                    ),
                }
            ),
            turn_context=TurnContext(
                has_initiated_action=True,
                tactical_action_step=TacticalActionStep.MOVEMENT,
                active_system_id=0,
            ),
            ships=frozenset({ship}),
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


def _setup_simple_movement_scenario(active_system_id: int) -> GameState:
    player_a = Player(
        "A", strategy_cards=(StrategyCard(name="Leadership", initiative=1, is_ready=True),)
    )
    ship = Ship(
        ship_id=0,
        owner_name="A",
        kind=ShipKind.DREADNOUGHT,
        stats=ShipStats(cost=4, combat=5, move=1, capacity=1),
    )
    system_0 = System(
        id=0,
        command_tokens=(CommandToken("A"),) if active_system_id == 0 else (),
        coordinates=HexCoord(0, 0),
        ships=frozenset({ship}),
    )
    system_1 = System(
        id=1,
        command_tokens=(CommandToken("A"),) if active_system_id == 1 else (),
        coordinates=HexCoord(0, 1),
    )
    system_2 = System(
        id=2,
        command_tokens=(CommandToken("A"),) if active_system_id == 2 else (),
        coordinates=HexCoord(0, 2),
    )

    return GameState(
        players=(player_a,),
        active_player=player_a,
        phase=Phase.ACTION,
        galaxy=frozenset({system_0, system_1, system_2}),
        turn_context=TurnContext(
            has_initiated_action=True,
            tactical_action_step=TacticalActionStep.MOVEMENT,
            active_system_id=active_system_id,
        ),
        ships=frozenset({ship}),
    )


def test_89_2_a_ships_with_insufficient_move_cannot_move() -> None:
    state = _setup_simple_movement_scenario(active_system_id=2)
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


def test_89_2_a_ship_with_sufficient_move_may_move() -> None:
    state = _setup_simple_movement_scenario(active_system_id=1)
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


def test_89_2_b_active_player_may_move_no_ships() -> None:
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=3, strategy=0),
    )
    session = GameSession(
        initial_state=GameState(
            players=(player_a,),
            active_player=player_a,
            phase=Phase.ACTION,
            galaxy=frozenset({System(id=0, command_tokens=()), System(id=1, command_tokens=())}),
            turn_context=TurnContext(
                has_initiated_action=False, tactical_action_step=TacticalActionStep.MOVEMENT
            ),
        ),
        engine=get_default_game_engine(),
    )
    new_state = session.apply_command(
        Command(actor=player_a, command_type=CommandType.END_MOVEMENT)
    )
    assert new_state.turn_context.tactical_action_step == TacticalActionStep.SPACE_COMBAT


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
