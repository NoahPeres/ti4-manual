from ast import Add
from typing import TYPE_CHECKING

from src.engine.actions.tactical_action import (
    AdvanceToInvasionStepEvent,
    InvalidActiveSystemError,
)
from src.engine.core.command import Command, CommandRule, CommandType, ValidationResult
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import (
    Ability,
    GameState,
    Window,
    InvasionCommit,
    TacticalActionStep,
)
from src.engine.core.windows import CloseWindowEvent, OpenWindowEvent
from dataclasses import dataclass, replace

if TYPE_CHECKING:
    from collections.abc import Sequence


class OpenBombardmentWindowEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {AdvanceToInvasionStepEvent}

    def on_event(self, state: GameState, event: Event) -> list[Event]:
        del event
        if state.active_system is None:
            raise InvalidActiveSystemError
        return [OpenWindowEvent(window=Window.TACTICAL_ACTION_BOMBARDMENT)]


class ResolveBombardmentEvent(Event):
    def __repr__(self) -> str:
        return "ResolveBombardmentEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.use_ability_for_player(
            player=previous_state.active_player,
            ability=Ability.BOMBARDMENT,
        )  # TODO: Implement actual bombardment resolution logic.


class ResolveBombardmentCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "ResolveBombardmentCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_BOMBARDMENT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.TACTICAL_ACTION_BOMBARDMENT):
            return ValidationResult(
                is_valid=False,
                info="Cannot use bombardment outside of bombardment window.",
            )
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only active player can use bombardment.")
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> list[Event]:
        del state, command
        return [ResolveBombardmentEvent()]


class PassBombardmentCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassBombardmentCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_BOMBARDMENT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.TACTICAL_ACTION_BOMBARDMENT):
            return ValidationResult(
                is_valid=False,
                info="Cannot pass bombardment outside of bombardment window.",
            )
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only active player can pass bombardment.")
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> list[Event]:
        del state, command
        return [PassBombardmentEvent()]


class PassBombardmentEvent(Event):
    def __repr__(self) -> str:
        return "PassBombardmentEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.pass_on_window_for_player(
            player=previous_state.active_player,
            window=Window.TACTICAL_ACTION_BOMBARDMENT,
        )


class CloseBombardmentWindowEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolveBombardmentEvent, PassBombardmentEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if state.active_system is None:
            raise InvalidActiveSystemError
        if not state.player_may_resolve_bombardment_in_system(
            player=state.active_player,
            system_id=state.active_system.id,
        ):
            return [CloseWindowEvent(window=Window.TACTICAL_ACTION_BOMBARDMENT)]
        return []


@dataclass(frozen=True)
class CommitGroundForceCommand(Command):
    ground_force_id: int
    to_planet_id: int


class AddInvasionCommitToPendingEvent(Event):
    def __init__(self, ground_force_id: int, to_planet_id: int):
        self.ground_force_id: int = ground_force_id
        self.to_planet_id: int = to_planet_id

    def __repr__(self) -> str:
        return f"AddInvasionCommitToPendingEvent:{self.ground_force_id}:{self.to_planet_id})"

    def apply(self, previous_state: GameState) -> GameState:
        invasion_set = previous_state.turn_context.pending_invasion_commits | {
            InvasionCommit(ground_force_id=self.ground_force_id, to_planet_id=self.to_planet_id)
        }
        return replace(
            previous_state,
            turn_context=replace(
                previous_state.turn_context, pending_invasion_commits=invasion_set
            ),
        )


class CommitGroundForceCommandRule(CommandRule[CommitGroundForceCommand]):
    def __repr__(self) -> str:
        return "CommitGroundForceCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.COMMIT_GROUND_FORCE}

    def validate_legality(
        self, state: GameState, command: CommitGroundForceCommand
    ) -> ValidationResult:
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: CommitGroundForceCommand) -> Sequence[Event]:
        del state
        return [
            AddInvasionCommitToPendingEvent(
                ground_force_id=command.ground_force_id, to_planet_id=command.to_planet_id
            )
        ]


class ResolvePendingInvasionCommitsEvent(Event):
    def __repr__(self) -> str:
        return "ResolvePendingInvasionCommitsEvent"

    def apply(self, previous_state: GameState) -> GameState:
        new_state = previous_state
        committed_units = set()
        for commit in previous_state.turn_context.pending_invasion_commits:
            ground_force = new_state.get_ground_force_from_id(commit.ground_force_id)
            ground_force = ground_force.set_planet_id(commit.to_planet_id)
            committed_units.add(ground_force)
        committed_unit_ids = {unit.unit_id for unit in committed_units}
        return replace(
            new_state,
            units=frozenset(
                {unit for unit in previous_state.units if unit.unit_id not in committed_unit_ids}
                | committed_units
            ),
            turn_context=replace(new_state.turn_context, pending_invasion_commits=frozenset()),
        )


class EndInvasionCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "EndInvasionCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_INVASION}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.is_active_player(command.actor):
            return ValidationResult(is_valid=False, info="Only active player can end invasion.")
        if state.turn_context.tactical_action_step != TacticalActionStep.INVASION:
            return ValidationResult(
                is_valid=False,
                info="Can only end invasion during invasion step of tactical action.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state, command
        return [ResolvePendingInvasionCommitsEvent()]


def get_command_rules() -> list[CommandRule[CommitGroundForceCommand]]:
    return [
        ResolveBombardmentCommandRule(),
        PassBombardmentCommandRule(),
        EndInvasionCommandRule(),
        CommitGroundForceCommandRule(),
    ]


def get_event_rules() -> list[EventRule]:
    return [OpenBombardmentWindowEventRule(), CloseBombardmentWindowEventRule()]
