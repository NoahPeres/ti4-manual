from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    ValidationResult,
)
from src.engine.core.event import Event
from src.engine.core.game_state import GameState, Window
from src.engine.units.units import UnitAbility

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.event import EventRule
    from src.engine.core.game_engine import EngineContext


@dataclass(frozen=True)
class SustainDamageCommand(Command):
    unit_id: int


class SustainDamageEvent(Event):
    def __init__(self, unit_id: int) -> None:
        self.unit_id = unit_id

    def apply(self, previous_state: GameState) -> GameState:
        new_unit = previous_state.get_unit_from_id(self.unit_id).set_is_damaged(is_damaged=True)
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().cancel_hit(
                player_name=new_unit.owner_name,
            ),
        ).replace_unit(new_unit)

    def __repr__(self) -> str:
        return f"SustainDamageEvent:{self.unit_id}"


class SustainDamageCommandRule(CommandRule[SustainDamageCommand]):
    def __repr__(self) -> str:
        return "SustainDamageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_SUSTAIN_DAMAGE}

    def validate_legality(
        self,
        state: GameState,
        command: SustainDamageCommand,
    ) -> ValidationResult:
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
        unit = state.get_unit_from_id(unit_id=command.unit_id)
        if UnitAbility.SUSTAIN_DAMAGE not in unit.stats.unit_abilities:
            return ValidationResult(
                is_valid=False,
                info="Unit does not have the SUSTAIN DAMAGE ability.",
            )
        if unit.owner_name != command.actor:
            return ValidationResult(
                is_valid=False,
                info="You cannot use abilities for units which aren't yours.",
            )
        if unit.is_damaged:
            return ValidationResult(is_valid=False, info="Unit is already damaged.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: SustainDamageCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [SustainDamageEvent(unit_id=command.unit_id)]

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
            if UnitAbility.SUSTAIN_DAMAGE in unit.stats.unit_abilities
        ]


def get_command_rules() -> list[CommandRule[SustainDamageCommand]]:
    return [SustainDamageCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
