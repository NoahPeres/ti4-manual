from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.command import CommandRule
    from src.engine.core.event import EventRule


class RulesEngine(Protocol):
    """command_rules: A sequence of CommandRule instances that define how commands are processed.
    event_rules: A sequence of EventRule instances that define how events are processed (into more
    events).
    """

    command_rules: Sequence[CommandRule]
    event_rules: Sequence[EventRule]


class TI4RulesEngine(RulesEngine):
    def __init__(self) -> None:
        self.command_rules: Sequence[CommandRule] = []
        self.event_rules: Sequence[EventRule] = []
