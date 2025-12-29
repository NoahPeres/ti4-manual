from collections.abc import Sequence

from src.engine.core.command import CommandRule
from src.engine.core.event import EventRule
from src.engine.core.rules_engine import RulesEngine
from src.engine.turns import end_turn


class TI4RulesEngine(RulesEngine):
    def __init__(self) -> None:
        self.command_rules: Sequence[CommandRule] = end_turn.get_rules()
        self.event_rules: Sequence[EventRule] = []
