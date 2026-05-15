from typing import TYPE_CHECKING

from src.engine.actions.tactical_action import (
    AdvanceToInvasionStepEvent,
    AdvanceToSpaceCombatStepEvent,
)
from src.engine.core.command import Command, CommandRule
from src.engine.core.event import Event, EventRule

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.game_state import GameState


class SkipSpaceCombatIfOnlyOnePlayerHasShips(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {AdvanceToSpaceCombatStepEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if state.active_system is None:
            raise ValueError("Cannot find active system.")
        units_in_active_system_system = state.get_units_in_system(state.active_system.id)
        if len({unit.owner_name for unit in units_in_active_system_system}) <= 1:
            return [AdvanceToInvasionStepEvent()]
        return []


def get_command_rules() -> list[CommandRule[Command]]:
    return []


def get_event_rules() -> list[EventRule]:
    return [SkipSpaceCombatIfOnlyOnePlayerHasShips()]
