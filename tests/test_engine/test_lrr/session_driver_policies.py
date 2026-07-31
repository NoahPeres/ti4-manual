from typing import TYPE_CHECKING, Callable

from src.driver.game_driver import OptionalCommandPolicy, PriorityPolicy
from src.engine.actions.space_combat import AssignHitCommand
from src.engine.core.command import Command, CommandType

if TYPE_CHECKING:
    from collections.abc import Iterable

    from src.engine.core.game_state import GameState


class DoCommandIfOnlyOneLegal(OptionalCommandPolicy):
    def select_command(self, state: GameState, legal_commands: Iterable[Command]) -> Command | None:
        del state
        legal_commands_list = list(legal_commands)
        if len(legal_commands_list) == 1:
            return legal_commands_list[0]
        return None


class PassOnSustainDamage(OptionalCommandPolicy):
    def select_command(self, state: GameState, legal_commands: Iterable[Command]) -> Command | None:
        del state
        for command in legal_commands:
            if command.command_type == CommandType.PASS_BEFORE_ASSIGN_HITS:
                return command
        return None


class SelectFirstLegalCommand(OptionalCommandPolicy):
    def select_command(self, state: GameState, legal_commands: Iterable[Command]) -> Command | None:
        del state
        for command in legal_commands:
            return command
        return None


class SelectPlayerPriority(OptionalCommandPolicy):
    def __init__(self, priority: list[str]) -> None:
        self.player_priority = priority

    def select_command(self, state: GameState, legal_commands: Iterable[Command]) -> Command | None:
        del state
        legal_commands = list(legal_commands)
        for name in self.player_priority:
            commands = [command for command in legal_commands if command.actor == name]
            if len(commands) == 1:
                return commands[0]
        return None


class AssignHitInOrder(OptionalCommandPolicy):
    def __init__(self, order_function: Callable[[list[int]], int]) -> None:
        self.order_function = order_function

    def select_command(self, state: GameState, legal_commands: Iterable[Command]) -> Command | None:
        del state
        commands = [
            command
            for command in legal_commands
            if command.command_type == CommandType.ASSIGN_HIT
            and isinstance(command, AssignHitCommand)
        ]
        if len(commands) == 0:
            return None
        selected_unit_id = self.order_function([command.unit_id for command in commands])
        return [command for command in commands if command.unit_id == selected_unit_id][0]


DEFAULT_PRIORITIES: list[OptionalCommandPolicy] = [
    DoCommandIfOnlyOneLegal(),
    PassOnSustainDamage(),
    SelectPlayerPriority(["A", "B"]),
    AssignHitInOrder(min),
]


def make_dumb_space_combat_agent(
    additional_policies: list[OptionalCommandPolicy],
    *,
    select_first_legal_command: bool = False,
) -> PriorityPolicy:
    policies = additional_policies + DEFAULT_PRIORITIES
    if select_first_legal_command:
        policies.append(SelectFirstLegalCommand())
    return PriorityPolicy(sub_policies=policies)


class UseSustainDamage(OptionalCommandPolicy):
    def select_command(self, state: GameState, legal_commands: Iterable[Command]) -> Command | None:
        del state
        sustain_damage_commands = [
            command
            for command in legal_commands
            if command.command_type == CommandType.USE_SUSTAIN_DAMAGE
        ]
        if len(sustain_damage_commands) == 0:
            return None
        return sustain_damage_commands[0]


class UseAFB(OptionalCommandPolicy):
    def select_command(self, state: GameState, legal_commands: Iterable[Command]) -> Command | None:
        del state
        sustain_damage_commands = [
            command
            for command in legal_commands
            if command.command_type == CommandType.USE_ANTI_FIGHTER_BARRAGE
        ]
        if len(sustain_damage_commands) == 0:
            return None
        return sustain_damage_commands[0]


class DoNotRetreat(OptionalCommandPolicy):
    def select_command(self, state: GameState, legal_commands: Iterable[Command]) -> Command | None:
        del state
        commands = tuple(legal_commands)
        if any(command.command_type == CommandType.ANNOUNCE_RETREAT for command in commands):
            return next(
                (
                    command
                    for command in commands
                    if command.command_type == CommandType.PASS_ANNOUNCE_RETREAT
                ),
                None,
            )
        return None
