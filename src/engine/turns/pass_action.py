import dataclasses
from collections.abc import Sequence

from src.engine.core.command import Command, CommandRule, CommandRuleWhenApplicable, CommandType
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, Player, TurnContext


class PassEvent(Event):
    payload = "PassAction"

    def apply(self, previous_state: GameState) -> GameState:
        passed_player: Player = dataclasses.replace(previous_state.active_player, has_passed=True)
        new_players: tuple[Player, ...] = tuple(
            player if player != previous_state.active_player else passed_player
            for player in previous_state.players
        )
        return GameState(
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

    def is_legal_given_applicable(self, state: GameState, command: Command) -> bool:
        return state.active_player == command.actor

    def derive_events_given_applicable(self, state: GameState, command: Command) -> Sequence[Event]:
        return [PassEvent()]


def get_command_rules() -> list[CommandRule]:
    return [PassCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
