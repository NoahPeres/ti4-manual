from src.engine.core.game_engine import GameEngine
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import (
    GameState,
    HexCoord,
    Phase,
    System,
    TacticalActionStep,
    TurnContext,
)
from src.engine.core.invariants import make_all_invariants
from src.engine.core.player import CommandSheet, Player
from src.engine.core.ti4_rules_engine import TI4RulesEngine
from src.engine.strategy_cards import StrategyCard
from src.engine.tokens import CommandToken
from src.engine.units.units import ShipKind, Unit, make_unit_with_id


def get_default_game_engine() -> GameEngine:
    return GameEngine(rules_engine=TI4RulesEngine(), invariants=make_all_invariants())


def make_basic_session_from_players(players: tuple[Player, ...]) -> GameSession:
    engine = get_default_game_engine()
    if len(players) == 0:
        raise ValueError("Require non zero number of players to generate valid session.")
    return GameSession(
        initial_state=GameState(
            players=players,
            active_player=players[0],
            phase=Phase.ACTION,
            galaxy=frozenset({System(id=0, command_tokens=()), System(id=1, command_tokens=())}),
        ),
        engine=engine,
    )


def make_player(
    name: str,
    strategy_cards: tuple[StrategyCard, ...] = (),
) -> Player:
    return Player(
        name=name,
        strategy_cards=strategy_cards,
        command_sheet=CommandSheet.make_from_int(name, tactic=3, fleet=3, strategy=2),
        has_passed=False,
    )


def make_tactical_action_state(
    active_system_id: int,
    units: frozenset[Unit] | None = None,
    player_name: str = "A",
    num_systems: int = 3,
) -> GameState:
    """Create a GameState in the MOVEMENT step of a tactical action.

    Args:
        active_system_id: The ID of the system that is currently active
        units: Frozenset of units to include in the state. If None, includes a default
               Dreadnought ship at system 0
        player_name: Name of the active player (defaults to "A")
        num_systems: Number of systems to create with sequential coordinates (defaults to 3)

    Returns:
        A GameState ready for movement phase testing
    """
    if units is None:
        # Create default ship at system 0
        default_ship = make_unit_with_id(
            unit_id=0,
            owner_name=player_name,
            kind=ShipKind.DREADNOUGHT,
            system_id=0,
        )
        units = frozenset({default_ship})

    player = Player(
        name=player_name,
        strategy_cards=(StrategyCard(name="Leadership", initiative=1, is_ready=True),),
    )

    # Create systems with coordinates in a line
    systems = frozenset(
        System(
            id=system_id,
            command_tokens=(CommandToken(player_name),) if system_id == active_system_id else (),
            coordinates=HexCoord(0, system_id),
        )
        for system_id in range(num_systems)
    )

    return GameState(
        players=(player,),
        active_player=player,
        phase=Phase.ACTION,
        galaxy=systems,
        turn_context=TurnContext(
            has_initiated_action=True,
            tactical_action_step=TacticalActionStep.MOVEMENT,
            active_system_id=active_system_id,
        ),
        units=units,
    )
