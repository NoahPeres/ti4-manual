from typing import Protocol
from src.engine.core.command import CommandRule
from collections.abc import Sequence

from src.engine.core.event import EventRule


class RulesEngine(Protocol):
    """
    command_rules: A sequence of CommandRule instances that define how commands are processed.
    event_rules: A sequence of EventRule instances that define how events are processed (into more events).
    """

    command_rules: Sequence[CommandRule]
    event_rules: Sequence[EventRule]
