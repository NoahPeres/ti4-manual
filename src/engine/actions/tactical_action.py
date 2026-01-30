from collections.abc import Sequence
from dataclasses import dataclass, replace

from src.engine.core.command import Command, CommandRule, CommandRuleWhenApplicable, CommandType
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState
from src.engine.core.player import CommandSheet
from src.engine.tokens import CommandToken


@dataclass(frozen=True)
class ActivateCommand(Command):
    system_id: int


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
        )


class TacticalActionCompletedEvent(Event):
    payload: str = "TacticalActionCompletedEvent"

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

    def is_legal_given_applicable(self, state: GameState, command: ActivateCommand) -> bool:
        try:
            system = state.get_system(id=command.system_id)
        except ValueError:
            return False
        return (
            (state.active_player == command.actor)
            and not state.has_taken_turn
            and not any(token.player_name == command.actor.name for token in system.command_tokens)
            and len(command.actor.command_sheet.tactic) > 0
        )

    def derive_events_given_applicable(
        self, state: GameState, command: ActivateCommand
    ) -> Sequence[Event]:
        return [
            ActivateSystemEvent(player_id=command.actor.name, system_id=command.system_id),
            TacticalActionCompletedEvent(),
        ]


def get_command_rules() -> list[CommandRule]:
    return [InitiateTacticalActionCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
