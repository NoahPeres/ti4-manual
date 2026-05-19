from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, TacticalActionStep
from src.engine.tokens import CommandToken

if TYPE_CHECKING:
    from collections.abc import Sequence


class InvalidActiveSystemError(ValueError):
    def __init__(self, message: str = "Active system not found") -> None:
        super().__init__(message)


@dataclass(frozen=True)
class ActivateCommand(Command):
    system_id: int


class ActivateSystemEvent(Event):
    def __init__(self, player_id: str, system_id: int) -> None:
        self.system_id: int = system_id
        self.player_id: str = player_id

    def __repr__(self) -> str:
        return f"ActivateSystemEvent:{self.system_id}:{self.player_id}"

    def apply(self, previous_state: GameState) -> GameState:
        active_system = previous_state.get_system(system_id=self.system_id)
        new_system = replace(
            active_system,
            command_tokens=(
                *active_system.command_tokens,
                CommandToken(player_name=self.player_id),
            ),
        )
        new_galaxy = frozenset(
            {system for system in previous_state.galaxy if system.id != self.system_id},
        ) | {new_system}
        old_player = previous_state.get_player(name=self.player_id)
        new_player = replace(
            old_player,
            command_sheet=replace(
                old_player.command_sheet,
                tactic=old_player.command_sheet.tactic[1:],
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


def _make_advance_to_step_event(step: TacticalActionStep) -> type[Event]:
    class AdvanceToStepEvent(Event):
        def __repr__(self) -> str:
            return f"AdvanceTo{step.name}Step"

        def apply(self, previous_state: GameState) -> GameState:
            return replace(
                previous_state,
                turn_context=replace(previous_state.turn_context, tactical_action_step=step),
            )

    AdvanceToStepEvent.__name__ = f"AdvanceTo{step.name}StepEvent"
    AdvanceToStepEvent.__qualname__ = f"AdvanceTo{step.name}StepEvent"
    return AdvanceToStepEvent


AdvanceToMovementStepEvent = _make_advance_to_step_event(TacticalActionStep.MOVEMENT)
AdvanceToSpaceCombatStepEvent = _make_advance_to_step_event(TacticalActionStep.SPACE_COMBAT)
AdvanceToInvasionStepEvent = _make_advance_to_step_event(TacticalActionStep.INVASION)
AdvanceToProductionStepEvent = _make_advance_to_step_event(TacticalActionStep.PRODUCTION)


class TacticalActionInitiatedEvent(Event):
    def __repr__(self) -> str:
        return "TacticalActionInitiatedEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return replace(
            previous_state,
            turn_context=replace(previous_state.turn_context, has_initiated_action=True),
        )


class InitiateTacticalActionCommandRule(CommandRule[ActivateCommand]):
    def __repr__(self) -> str:
        return "InitiateTacticalAction"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.INITIATE_TACTICAL_ACTION}

    def validate_legality(self, state: GameState, command: ActivateCommand) -> ValidationResult:
        try:
            system = state.get_system(system_id=command.system_id)
        except ValueError:
            return ValidationResult(is_valid=False, info="System not found")
        if not state.is_active_player(command.actor):
            return ValidationResult(
                is_valid=False,
                info="Only the active player can initiate a tactical action",
            )
        if state.has_taken_turn:
            return ValidationResult(is_valid=False, info="Player has already taken a turn")
        if system.has_command_token(command.actor):
            return ValidationResult(
                is_valid=False,
                info="Cannot activate a system with your command token",
            )
        if len(command.actor.command_sheet.tactic) == 0:
            return ValidationResult(
                is_valid=False,
                info="Player must have tokens in their tactic pool to perform tactical action",
            )
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: ActivateCommand) -> Sequence[Event]:
        del state
        return [
            ActivateSystemEvent(player_id=command.actor.name, system_id=command.system_id),
            TacticalActionInitiatedEvent(),
            AdvanceToMovementStepEvent(),
        ]


def get_command_rules() -> list[CommandRule[ActivateCommand]]:
    return [InitiateTacticalActionCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
