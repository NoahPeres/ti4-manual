import dataclasses
from typing import TYPE_CHECKING

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    EngineContext,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.game_state import GameState
    from src.engine.core.player import Player


class EndTurnEvent(Event):
    def __repr__(self) -> str:
        return "EndTurnEvent"

    def apply(self, previous_state: GameState) -> GameState:
        current_initiative = previous_state.active_player.initiative
        higher_initiatives = [
            player
            for player in previous_state.initiative_order_unpassed
            if player.initiative > current_initiative
        ]
        lower_initiatives = [
            player
            for player in previous_state.initiative_order_unpassed
            if player.initiative <= current_initiative
        ]
        next_player: Player
        if higher_initiatives:
            next_player = min(higher_initiatives, key=lambda x: x.initiative)
        elif lower_initiatives:
            next_player = min(lower_initiatives, key=lambda x: x.initiative)
        else:
            next_player = min(previous_state.initiative_order, key=lambda x: x.initiative)
        return dataclasses.replace(
            previous_state,
            active_player_name=next_player.name,
            turn_context=dataclasses.replace(
                previous_state.turn_context,
                has_initiated_action=False,
            ),
        )


class EndTurn(CommandRule[Command]):
    def __repr__(self) -> str:
        return "EndTurn"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_TURN}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.is_active_player(command.actor):
            return ValidationResult(
                is_valid=False,
                info="Only the active player can end their turn",
            )
        if not state.has_taken_turn:
            return ValidationResult(
                is_valid=False,
                info="A player must take a turn before ending it",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return [EndTurnEvent()]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        return [Command(actor=state.active_player, command_type=CommandType.END_TURN)]


def get_command_rules() -> list[CommandRule[Command]]:
    return [EndTurn()]


def get_event_rules() -> list[EventRule]:
    return []
