from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    ValidationResult,
)
from src.engine.core.game_state import GameState, Window

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.event import Event, EventRule
    from src.engine.core.game_engine import EngineContext


@dataclass(frozen=True)
class SustainDamageCommand(Command):
    unit_id: int


class SustainDamageCommandRule(CommandRule[SustainDamageCommand]):
    def __repr__(self) -> str:
        return "SustainDamageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_SUSTAIN_DAMAGE}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if command.actor != state.turn_context.get_space_combat_context().current_hits_assignee:
            return ValidationResult(
                is_valid=False,
                info="This is not your assign hits window.",
            )
        if not state.window_context.is_window_active(Window.BEFORE_ASSIGNING_HITS):
            return ValidationResult(
                is_valid=False,
                info="Can only use SUSTAIN DAMAGE before assigning hits.",
            )
        # TODO: Proper sustain damage logic
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return []

    @staticmethod
    def candidate_commands(state: GameState) -> list[SustainDamageCommand]:
        if state.turn_context.space_combat_context is None:
            return []
        return [
            SustainDamageCommand(
                actor=player.name,
                command_type=CommandType.USE_SUSTAIN_DAMAGE,
                unit_id=unit.unit_id,
            )
            for player in state.players
            for unit in state.get_units_in_system(
                system_id=state.get_active_system().id,
                player_name=player.name,
            )
        ]


def get_command_rules() -> list[CommandRule[SustainDamageCommand]]:
    return [SustainDamageCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
