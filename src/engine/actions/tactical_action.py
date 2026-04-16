from collections.abc import Sequence
from dataclasses import dataclass, replace

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandRuleWhenApplicable,
    CommandType,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, TacticalActionStep
from src.engine.tokens import CommandToken


@dataclass(frozen=True)
class ActivateCommand(Command):
    system_id: int


@dataclass(frozen=True)
class MoveShipCommand(Command):
    ship_id: int
    to_system_id: int


class ActivateSystemEvent(Event):
    def __init__(self, player_id: str, system_id: int) -> None:
        self.system_id: int = system_id
        self.player_id: str = player_id

    payload: str = "ActivateSystemEvent"

    def apply(self, previous_state: GameState) -> GameState:
        active_system = previous_state.get_system(id=self.system_id)
        new_system = replace(
            active_system,
            command_tokens=(
                *active_system.command_tokens,
                CommandToken(player_name=self.player_id),
            ),
        )
        new_galaxy = {
            system for system in previous_state.galaxy if system.id != self.system_id
        }.union({new_system})
        old_player = previous_state.get_player(name=self.player_id)
        new_player = replace(
            old_player,
            command_sheet=replace(
                old_player.command_sheet, tactic=old_player.command_sheet.tactic[1:]
            ),
        )
        players = tuple(
            new_player if player.name == self.player_id else player
            for player in previous_state.players
        )

        return replace(
            previous_state,
            galaxy=new_galaxy,
            players=players,
            turn_context=replace(
                previous_state.turn_context,
                tactical_action_step=TacticalActionStep.ACTIVATION,
                active_system_id=self.system_id,
            ),
        )


class AdvanceToMovementStep(Event):
    payload = "AdvanceToMovementStep"

    def apply(self, previous_state: GameState) -> GameState:
        return replace(
            previous_state,
            turn_context=replace(
                previous_state.turn_context, tactical_action_step=TacticalActionStep.MOVEMENT
            ),
        )


class AdvanceToSpaceCombatStep(Event):
    payload = "AdvanceToSpaceCombatStep"

    def apply(self, previous_state: GameState) -> GameState:
        return replace(
            previous_state,
            turn_context=replace(
                previous_state.turn_context, tactical_action_step=TacticalActionStep.SPACE_COMBAT
            ),
        )


class TacticalActionInitiatedEvent(Event):
    payload: str = "TacticalActionInitiatedEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return replace(
            previous_state, turn_context=replace(previous_state.turn_context, has_taken_action=True)
        )


class InitiateTacticalActionCommandRule(CommandRuleWhenApplicable[ActivateCommand]):
    def __repr__(self) -> str:
        return "InitiateTacticalAction"

    @staticmethod
    def is_applicable(command: Command) -> bool:
        return command.command_type == CommandType.INITIATE_TACTICAL_ACTION

    def is_legal_given_applicable(
        self, state: GameState, command: ActivateCommand
    ) -> ValidationResult:
        try:
            system = state.get_system(id=command.system_id)
        except ValueError:
            return ValidationResult(is_valid=False, info="System not found")
        if state.active_player != command.actor:
            return ValidationResult(
                is_valid=False, info="Only the active player can initiate a tactical action"
            )
        if state.has_taken_turn:
            return ValidationResult(is_valid=False, info="Player has already taken a turn")
        if any(token.player_name == command.actor.name for token in system.command_tokens):
            return ValidationResult(
                is_valid=False,
                info="Cannot activate a system with your command token",
            )
        if len(command.actor.command_sheet.tactic) == 0:
            return ValidationResult(
                is_valid=False,
                info="Player must have tokens in their tactic pool to perform tactical action",
            )
        return ValidationResult(True)

    def derive_events_given_applicable(
        self, state: GameState, command: ActivateCommand
    ) -> Sequence[Event]:
        return [
            ActivateSystemEvent(player_id=command.actor.name, system_id=command.system_id),
            TacticalActionInitiatedEvent(),
            AdvanceToMovementStep(),
        ]


class EndMovementCommandRule(CommandRuleWhenApplicable[Command]):
    def __repr__(self) -> str:
        return "EndMovement"

    @staticmethod
    def is_applicable(command: Command) -> bool:
        return command.command_type == CommandType.END_MOVEMENT

    def is_legal_given_applicable(self, state: GameState, command: Command) -> ValidationResult:
        if not state.active_player == command.actor:
            return ValidationResult(is_valid=False, info="Only the active player can end movement")
        if not state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT:
            return ValidationResult(
                is_valid=False,
                info="Can only end movement during the movement step of a tactical action",
            )
        return ValidationResult(is_valid=True)

    def derive_events_given_applicable(self, state: GameState, command: Command) -> Sequence[Event]:
        return [AdvanceToSpaceCombatStep()]


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
        ship = state.get_ship_from_id(id=command.ship_id)
        owner = state.get_player(name=ship.owner_name)
        active_system = state.active_system
        current_system = state.get_current_system(ship)
        if active_system is None:
            return ValidationResult(is_valid=False, info="No active system")
        if current_system is None:
            return ValidationResult(is_valid=False, info="Ship is not in any system")
        if not state.active_player == command.actor:
            return ValidationResult(is_valid=False, info="Only the active player can move ships")
        if not state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT:
            return ValidationResult(
                is_valid=False,
                info="Can only move ships during the movement step of a tactical action",
            )
        if not command.actor == owner:
            return ValidationResult(is_valid=False, info="Player can only move their own ships")
        if not command.to_system_id == active_system.id:
            return ValidationResult(is_valid=False, info="Can only move ships to the active system")
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
    return [InitiateTacticalActionCommandRule(), EndMovementCommandRule(), MoveShipCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
