from src.engine.core.game_engine import GameEngine
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import GameState, Phase, System
from src.engine.core.invariants import make_all_invariants
from src.engine.core.player import CommandSheet, Player, StrategyCard
from src.engine.core.ti4_rules_engine import TI4RulesEngine


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
