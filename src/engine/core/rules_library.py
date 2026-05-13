from typing import TYPE_CHECKING, Protocol, cast

from src.engine.actions import movement, tactical_action
from src.engine.turns import end_turn, pass_action

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.command import Command, CommandRule
    from src.engine.core.event import EventRule


class RulesModule(Protocol):
    def get_command_rules(self) -> list[CommandRule[Command]]: ...

    def get_event_rules(self) -> list[EventRule]: ...


MODULES_WITH_RULES: Sequence[RulesModule] = [
    cast("RulesModule", module)
    for module in [
        end_turn,
        tactical_action,
        pass_action,
        movement,
    ]
]


def get_command_rules() -> list[CommandRule[Command]]:
    rules: list[CommandRule[Command]] = []
    for module in MODULES_WITH_RULES:
        rules.extend(module.get_command_rules())
    return rules


def get_event_rules() -> list[EventRule]:
    rules: list[EventRule] = []
    for module in MODULES_WITH_RULES:
        rules.extend(module.get_event_rules())
    return rules
