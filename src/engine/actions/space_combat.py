from typing import TYPE_CHECKING

from src.engine.actions.tactical_action import (
    AdvanceToInvasionStepEvent,
    AdvanceToSpaceCombatStepEvent,
    InvalidActiveSystemError,
)
from src.engine.core.command import Command, CommandRule, CommandType, ValidationResult
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, TacticalActionStep

if TYPE_CHECKING:
    from collections.abc import Sequence


class SkipSpaceCombatIfOnlyOnePlayerHasShips(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {AdvanceToSpaceCombatStepEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if state.active_system is None:
            raise InvalidActiveSystemError
        if (
            len({unit.owner_name for unit in state.get_ships_in_system(state.active_system.id)})
            <= 1
        ):
            return [AdvanceToInvasionStepEvent()]
        return [ResolveSpaceCombatEvent()]


class EndSpaceCombatCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "EndSpaceCombatCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_SPACE_COMBAT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only active player can end space combat.")
        if state.turn_context.tactical_action_step != TacticalActionStep.SPACE_COMBAT:
            return ValidationResult(
                is_valid=False,
                info="Can only end space combat during space combat window.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> list[Event]:
        del state, command
        return [AdvanceToInvasionStepEvent()]


class ResolveSpaceCombatEvent(Event):
    def __repr__(self) -> str:
        return "ResolveSpaceCombatEvent"

    def apply(self, previous_state: GameState) -> GameState:
        # Placeholder implementation - replace with actual space combat resolution logic
        return previous_state


def get_command_rules() -> list[CommandRule[Command]]:
    return [EndSpaceCombatCommandRule()]


def get_event_rules() -> list[EventRule]:
    return [SkipSpaceCombatIfOnlyOnePlayerHasShips()]
