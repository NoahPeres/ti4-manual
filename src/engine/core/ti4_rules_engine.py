from collections.abc import Sequence

from src.engine.core import rules_library
from src.engine.core.command import CommandRule
from src.engine.core.event import EventRule
from src.engine.core.rules_engine import RulesEngine


class TI4RulesEngine(RulesEngine):
    def __init__(self) -> None:
        self.command_rules: Sequence[CommandRule] = rules_library.get_command_rules()
        self.event_rules: Sequence[EventRule] = rules_library.get_event_rules()
