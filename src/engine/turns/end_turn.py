import dataclasses
from collections.abc import Sequence

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandRuleWhenApplicable,
    CommandType,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState
from src.engine.core.player import Player


class EndTurnEvent(Event):
    payload: str = "EndTurnEvent"

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
            active_player=next_player,
            turn_context=dataclasses.replace(previous_state.turn_context, has_taken_action=False),
        )


class EndTurn(CommandRuleWhenApplicable):
    def __repr__(self) -> str:
        return "EndTurn"

    @staticmethod
    def is_applicable(command: Command) -> bool:
        return command.command_type == CommandType.END_TURN

    def is_legal_given_applicable(self, state: GameState, command: Command) -> ValidationResult:
        if not state.is_active_player(command.actor):
            return ValidationResult(
                is_valid=False, info="Only the active player can end their turn"
            )
        if not state.has_taken_turn:
            return ValidationResult(
                is_valid=False, info="A player must take a turn before ending it"
            )
        return ValidationResult(is_valid=True)

    def derive_events_given_applicable(self, state: GameState, command: Command) -> Sequence[Event]:
        return [EndTurnEvent()]


def get_command_rules() -> list[CommandRule]:
    return [EndTurn()]


def get_event_rules() -> list[EventRule]:
    return []
