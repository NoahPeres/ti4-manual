from collections.abc import Sequence
from typing import Mapping, Protocol

from src.engine.core.command import Command, CommandRule, CommandType
from src.engine.core.event import EventRule
from src.engine.core.game_state import Window


class RulesEngine(Protocol):
    command_rules: Sequence[CommandRule[Command]]
    event_rules: Sequence[EventRule]
    allowed_commands_by_window: Mapping[Window, tuple[CommandType, ...]]
    check_all_rules_have_implementations: bool
