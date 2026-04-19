from collections.abc import Sequence
from dataclasses import dataclass

from src.engine.actions.tactical_action import AdvanceToSpaceCombatStepEvent
from src.engine.core.command import (
    Command,
    CommandRule,
    CommandRuleWhenApplicable,
    CommandType,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, TacticalActionStep


@dataclass(frozen=True)
class MoveShipCommand(Command):
    ship_id: int
    to_system_id: int


class EndMovementCommandRule(CommandRuleWhenApplicable[Command]):
    def __repr__(self) -> str:
        return "EndMovement"

    @staticmethod
    def is_applicable(command: Command) -> bool:
        return command.command_type == CommandType.END_MOVEMENT

    def is_legal_given_applicable(self, state: GameState, command: Command) -> ValidationResult:
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only the active player can end movement")
        if state.turn_context.tactical_action_step != TacticalActionStep.MOVEMENT:
            return ValidationResult(
                is_valid=False,
                info="Can only end movement during the movement step of a tactical action",
            )
        return ValidationResult(is_valid=True)

    def derive_events_given_applicable(self, state: GameState, command: Command) -> Sequence[Event]:
        return [AdvanceToSpaceCombatStepEvent()]


class AddMoveToPendingEvent(Event):
    def __init__(self, ship_id: int, to_system_id: int) -> None:
        self.ship_id = ship_id
        self.to_system_id = to_system_id

    payload = "AddMoveToPending"

    def apply(self, previous_state: GameState) -> GameState:
        # TODO implement
        return previous_state


class MoveShipCommandRule(CommandRuleWhenApplicable[MoveShipCommand]):
    def __repr__(self) -> str:
        return "MoveShip"

    @staticmethod
    def is_applicable(command: Command) -> bool:
        return command.command_type == CommandType.MOVE_SHIP

    def is_legal_given_applicable(
        self, state: GameState, command: MoveShipCommand
    ) -> ValidationResult:
        if not state.is_active_player(command.actor):
            return ValidationResult(is_valid=False, info="Only the active player can move ships")
        if state.turn_context.tactical_action_step != TacticalActionStep.MOVEMENT:
            return ValidationResult(
                is_valid=False,
                info="Can only move ships during the movement step of a tactical action",
            )
        ship = state.get_ship_from_id(id=command.ship_id)
        try:
            owner = state.get_player(name=ship.owner_name)
        except ValueError:
            return ValidationResult(is_valid=False, info="Invalid ship owner")
        if command.actor != owner:
            return ValidationResult(is_valid=False, info="Player can only move their own ships")
        active_system = state.active_system
        if active_system is None:
            return ValidationResult(is_valid=False, info="No active system")
        if command.to_system_id != active_system.id:
            return ValidationResult(is_valid=False, info="Can only move ships to the active system")
        current_system = state.get_current_system(ship)
        if current_system is None:
            return ValidationResult(is_valid=False, info="Ship is not in any system")
        if current_system.has_command_token(state.active_player):
            return ValidationResult(
                is_valid=False, info="Cannot move ships from a system with your command token"
            )
        return ValidationResult(is_valid=True)

    def derive_events_given_applicable(
        self, state: GameState, command: MoveShipCommand
    ) -> Sequence[Event]:
        return [
            AddMoveToPendingEvent(
                ship_id=command.ship_id,
                to_system_id=command.to_system_id,
            )
        ]


def get_command_rules() -> list[CommandRule]:
    return [EndMovementCommandRule(), MoveShipCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
