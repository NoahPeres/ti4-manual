from typing import TYPE_CHECKING

from src.engine.core import rules_library
from src.engine.core.command import Command, CommandRule, CommandType
from src.engine.core.game_state import Window
from src.engine.core.rules_engine import RulesEngine

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.event import EventRule

_ALLOWED_COMMANDS_BY_WINDOW: dict[Window, tuple[CommandType, ...]] = {
    Window.AFTER_MOVE_SHIPS_STEP: (CommandType.USE_SPACE_CANNON, CommandType.PASS_SPACE_CANNON),
    Window.TACTICAL_ACTION_BOMBARDMENT: (CommandType.USE_BOMBARDMENT, CommandType.PASS_BOMBARDMENT),
    Window.START_OF_FIRST_ROUND_OF_SPACE_COMBAT: (CommandType.PASS_START_OF_COMBAT_ROUND,),
    Window.START_OF_SPACE_COMBAT: (CommandType.PASS_START_OF_COMBAT_ROUND,),
    Window.START_OF_SPACE_COMBAT_ROUND: (CommandType.PASS_START_OF_COMBAT_ROUND,),
}


class TI4RulesEngine(RulesEngine):
    check_all_rules_have_implementations = True
    allowed_commands_by_window = _ALLOWED_COMMANDS_BY_WINDOW

    def __init__(self) -> None:
        self.command_rules: Sequence[CommandRule[Command]] = rules_library.get_command_rules()
        self.event_rules: Sequence[EventRule] = rules_library.get_event_rules()
