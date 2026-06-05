import dataclasses
from dataclasses import replace
from typing import TYPE_CHECKING

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    EngineContext,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, Phase, TurnContext
from src.engine.turns.end_turn import EndTurnEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.player import Player


class PassEvent(Event):
    def __repr__(self) -> str:
        return "PassEvent"

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
            turn_context=TurnContext(has_initiated_action=False),
        )


class PassCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassAction"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_ACTION}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.is_active_player(command.actor):
            return ValidationResult(
                is_valid=False,
                info="Only the active player can pass their turn",
            )
        if not all(card.is_exhausted for card in state.active_player.strategy_cards):
            return ValidationResult(
                is_valid=False,
                info="All strategy cards must be exhausted to pass",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return [PassEvent(), EndTurnEvent()]


class AdvanceActionToStatusPhase(Event):
    def __repr__(self) -> str:
        return "AdvanceActionToStatusPhase"

    def apply(self, previous_state: GameState) -> GameState:
        return dataclasses.replace(previous_state, phase=Phase.STATUS)


class AdvanceToStatusRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {PassEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if len(state.initiative_order_unpassed) == 0:
            return [AdvanceActionToStatusPhase()]
        return []


def get_command_rules() -> list[CommandRule[Command]]:
    return [PassCommandRule()]


def get_event_rules() -> list[EventRule]:
    return [AdvanceToStatusRule()]
