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
    Window.END_OF_SPACE_COMBAT: (CommandType.PASS_END_OF_COMBAT_ROUND,),
    Window.END_OF_SPACE_COMBAT_ROUND: (CommandType.PASS_END_OF_COMBAT_ROUND,),
    Window.ANTI_FIGHTER_BARRAGE: (
        CommandType.USE_ANTI_FIGHTER_BARRAGE,
        CommandType.PASS_ANTI_FIGHTER_BARRAGE,
    ),
    Window.BEFORE_ASSIGNING_HITS: (
        CommandType.USE_SUSTAIN_DAMAGE,
        CommandType.PASS_BEFORE_ASSIGN_HITS,
    ),
    Window.MUST_CHOOSE_POOL_FOR_REMOVE_COMMAND_TOKEN: (CommandType.REMOVE_COMMAND_TOKEN_FROM_POOL,),
    Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY: (CommandType.REMOVE_UNIT,),
    Window.TRANSPORT_UNITS: (CommandType.TRANSPORT_UNIT, CommandType.PASS_TRANSPORT_UNIT),
}


class TI4RulesEngine(RulesEngine):
    check_all_rules_have_implementations = True
    allowed_commands_by_window = _ALLOWED_COMMANDS_BY_WINDOW

    def __init__(self) -> None:
        self.command_rules: Sequence[CommandRule[Command]] = rules_library.get_command_rules()
        self.event_rules: Sequence[EventRule] = rules_library.get_event_rules()
