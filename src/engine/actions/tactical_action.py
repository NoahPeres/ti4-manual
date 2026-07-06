from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    EngineContext,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import Galaxy, GameState, TacticalActionStep
from src.engine.core.player import CommandTokenPool
from src.engine.tokens import CommandToken

if TYPE_CHECKING:
    from collections.abc import Sequence


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
        active_system = previous_state.galaxy.get_system(system_id=self.system_id)
        new_system = replace(
            active_system,
            command_tokens=(
                *active_system.command_tokens,
                CommandToken(player_name=self.player_id),
            ),
        )
        new_galaxy = Galaxy(
            {system for system in previous_state.galaxy if system.id != self.system_id},
        ).combine(Galaxy({new_system}))
        old_player = previous_state.get_player(name=self.player_id)
        new_player = replace(
            old_player,
            command_sheet=old_player.command_sheet.remove_token_from_pool(
                command_token=CommandToken(player_name=old_player.name),
                pool=CommandTokenPool.TACTIC,
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
        system = state.galaxy.get_system(system_id=command.system_id)
        if not state.is_active_player(command.actor):
            return ValidationResult(
                is_valid=False,
                info="Only the active player can initiate a tactical action",
            )
        if state.has_taken_turn:
            return ValidationResult(is_valid=False, info="Player has already taken a turn")
        if state.turn_context.space_combat_context is not None:
            return ValidationResult(
                is_valid=False,
                info="Cannot initiate a tactical action during space combat",
            )
        if system.has_command_token(command.actor):
            return ValidationResult(
                is_valid=False,
                info="Cannot activate a system with your command token",
            )
        if len(state.get_player(command.actor).command_sheet.tactic) == 0:
            return ValidationResult(
                is_valid=False,
                info="Player must have tokens in their tactic pool to perform tactical action",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: ActivateCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [
            ActivateSystemEvent(player_id=command.actor, system_id=command.system_id),
            TacticalActionInitiatedEvent(),
            AdvanceToMovementStepEvent(),
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[ActivateCommand]:
        return [
            ActivateCommand(
                actor=state.active_player.name,
                command_type=CommandType.INITIATE_TACTICAL_ACTION,
                system_id=system.id,
            )
            for system in state.galaxy
        ]


def get_command_rules() -> list[CommandRule[ActivateCommand]]:
    return [InitiateTacticalActionCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
