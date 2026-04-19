import dataclasses
from collections.abc import Sequence
from dataclasses import replace

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandRuleWhenApplicable,
    CommandType,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, Phase, TurnContext
from src.engine.core.player import Player
from src.engine.turns.end_turn import EndTurnEvent


class PassEvent(Event):
    payload = "PassAction"

    def apply(self, previous_state: GameState) -> GameState:
        passed_player: Player = dataclasses.replace(previous_state.active_player, has_passed=True)
        new_players: tuple[Player, ...] = tuple(
            player if player != previous_state.active_player else passed_player
            for player in previous_state.players
        )
        return replace(
            previous_state,
            players=new_players,
            active_player=passed_player,
            turn_context=TurnContext(has_taken_action=False),
        )


class PassCommandRule(CommandRuleWhenApplicable):
    def __repr__(self) -> str:
        return "PassAction"

    @staticmethod
    def is_applicable(command: Command) -> bool:
        return command.command_type == CommandType.PASS_ACTION

    def is_legal_given_applicable(self, state: GameState, command: Command) -> ValidationResult:
        if not state.is_active_player(command.actor):
            return ValidationResult(
                is_valid=False, info="Only the active player can pass their turn"
            )
        if not all(card.is_exhausted for card in state.active_player.strategy_cards):
            return ValidationResult(
                is_valid=False, info="All strategy cards must be exhausted to pass"
            )
        return ValidationResult(is_valid=True)

    def derive_events_given_applicable(self, state: GameState, command: Command) -> Sequence[Event]:
        return [PassEvent(), EndTurnEvent()]


class AdvanceActionToStatusPhase(Event):
    payload = "AdvanceActionToStatusPhase"

    def apply(self, previous_state: GameState) -> GameState:
        return dataclasses.replace(previous_state, phase=Phase.STATUS)


class AdvanceToStatusRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        if (event.payload == "PassAction") and (len(state.initiative_order_unpassed) == 0):
            return [AdvanceActionToStatusPhase()]
        return []


def get_command_rules() -> list[CommandRule]:
    return [PassCommandRule()]


def get_event_rules() -> list[EventRule]:
    return [AdvanceToStatusRule()]
