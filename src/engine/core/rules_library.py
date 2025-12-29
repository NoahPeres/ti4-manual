from collections.abc import Sequence
from typing import Protocol, cast

from src.engine.core.command import CommandRule
from src.engine.core.event import EventRule
from src.engine.turns import end_turn
from src.engine.actions import tactical_action


class RulesModule(Protocol):
    def get_command_rules(self) -> list[CommandRule]: ...

    def get_event_rules(self) -> list[EventRule]: ...


MODULES_WITH_RULES: Sequence[RulesModule] = [
    cast(RulesModule, module)
    for module in [
        end_turn,
        tactical_action,
    ]
]


def get_command_rules() -> list[CommandRule]:
    rules: list[CommandRule] = []
    for module in MODULES_WITH_RULES:
        rules.extend(module.get_command_rules())
    return rules


def get_event_rules() -> list[EventRule]:
    rules: list[EventRule] = []
    for module in MODULES_WITH_RULES:
        if hasattr(module, "get_event_rules"):
            rules.extend(module.get_event_rules())
    return rules
