from src.engine.core.game_engine import GameEngine
from src.engine.core.invariants import make_all_invariants
from src.engine.core.ti4_rules_engine import TI4RulesEngine


def get_default_game_engine() -> GameEngine:
    return GameEngine(rules_engine=TI4RulesEngine(), invariants=make_all_invariants())
