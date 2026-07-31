from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.engine.actions.movement import OpenWindowEvent
from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    EngineContext,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, Window
from src.engine.core.windows import CloseWindowEvent

from .shared import get_active_system_id

if TYPE_CHECKING:
    from collections.abc import Sequence


class RemoveUnitEvent(Event):
    def __init__(self, unit_id: int) -> None:
        self.unit_id = unit_id

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.remove_unit(self.unit_id)

    def __repr__(self) -> str:
        return f"RemoveUnitEvent:{self.unit_id}"


@dataclass(frozen=True)
class RemoveUnitCommand(Command):
    unit_id: int


class RemoveUnitDueToCapacityCommandRule(CommandRule[RemoveUnitCommand]):
    def __repr__(self) -> str:
        return "RemoveUnit"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.REMOVE_UNIT}

    def validate_legality(self, state: GameState, command: RemoveUnitCommand) -> ValidationResult:
        if not state.window_context.is_window_active(Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY):
            return ValidationResult(is_valid=False, info="No reason to remove units.")
        unit = state.get_unit_from_id(command.unit_id)
        if unit.owner_name != command.actor:
            return ValidationResult(is_valid=False, info="You cannot remove another player's unit.")
        if not unit.is_transportable:
            return ValidationResult(
                is_valid=False,
                info="Unit is not transportable: removal won't alleviate capacity.",
            )
        if unit.system_id is None:
            return ValidationResult(is_valid=False, info="Unit is not in any system.")
        if not capacity_exceeded_in_system(state=state, system_id=unit.system_id):
            return ValidationResult(is_valid=False, info="Unit is not exceeding capacity.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: RemoveUnitCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [RemoveUnitEvent(unit_id=command.unit_id)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[RemoveUnitCommand]:
        if not state.window_context.is_window_active(Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY):
            return []
        units = {
            unit for unit in state.units if unit.is_transportable and unit.system_id is not None
        }
        return [
            RemoveUnitCommand(
                actor=unit.owner_name,
                command_type=CommandType.REMOVE_UNIT,
                unit_id=unit.unit_id,
            )
            for unit in units
            if unit.is_transportable
        ]


def capacity_exceeded_in_system(state: GameState, system_id: int) -> bool:
    units_in_space = state.get_units_in_space_area_of_system(system_id=system_id)
    if len({unit.owner_name for unit in units_in_space}) > 1:
        raise ValueError
    total_capacity = sum(
        [unit.stats.capacity for unit in units_in_space if unit.stats.capacity is not None],
    )
    total_capacity_required = sum([1 for unit in units_in_space if unit.is_transportable])
    return total_capacity_required > total_capacity


class CheckCapacityAfterCombatEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        if not isinstance(event, CloseWindowEvent):
            return []
        if event.window != Window.END_OF_SPACE_COMBAT:
            return []
        if not capacity_exceeded_in_system(state=state, system_id=get_active_system_id(state)):
            return []
        return [OpenWindowEvent(Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY)]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {CloseWindowEvent}


class ClearCombatStateEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(None)

    def __repr__(self) -> str:
        return "ClearCombatStateEvent"


class ClearCombatStateAfterCombatEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del state
        if not isinstance(event, CloseWindowEvent):
            return []
        if event.window != Window.END_OF_SPACE_COMBAT:
            return []
        return [ClearCombatStateEvent()]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {CloseWindowEvent}


class RecheckCapacityAfterRemovalEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if not state.window_context.is_window_active(Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY):
            return []
        if capacity_exceeded_in_system(state=state, system_id=get_active_system_id(state)):
            return []
        return [CloseWindowEvent(Window.MUST_REMOVE_UNITS_DUE_TO_CAPACITY)]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {RemoveUnitEvent}
