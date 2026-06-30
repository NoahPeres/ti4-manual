import itertools
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from src.engine.actions.tactical_action import (
    AdvanceToInvasionStepEvent,
    AdvanceToProductionStepEvent,
)
from src.engine.core.command import (
    CandidateCommandProvider,
    Command,
    CommandRule,
    CommandType,
    EngineContext,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import (
    Ability,
    GameState,
    InvalidActiveSystemError,
    InvasionCommit,
    TacticalActionStep,
    Window,
)
from src.engine.core.windows import CloseWindowEvent, OpenWindowEvent
from src.engine.units.units import GroundForce

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
        if not state.player_may_resolve_bombardment_in_system(
            player=state.active_player,
            system_id=state.get_active_system().id,
        ):
            return ValidationResult(
                is_valid=False,
                info="No valid targets for bombardment in active system.",
            )
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only active player can use bombardment.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> list[Event]:
        del state, command, engine_context
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

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> list[Event]:
        del state, command, engine_context
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
        if not state.player_may_resolve_bombardment_in_system(
            player=state.active_player,
            system_id=state.get_active_system().id,
        ):
            return [CloseWindowEvent(window=Window.TACTICAL_ACTION_BOMBARDMENT)]
        return []


@dataclass(frozen=True)
class CommitGroundForceCommand(Command):
    ground_force_id: int
    to_planet_id: int


class AddInvasionCommitToPendingEvent(Event):
    def __init__(self, ground_force_id: int, to_planet_id: int) -> None:
        self.ground_force_id: int = ground_force_id
        self.to_planet_id: int = to_planet_id

    def __repr__(self) -> str:
        return f"AddInvasionCommitToPendingEvent:{self.ground_force_id}:{self.to_planet_id}"

    def apply(self, previous_state: GameState) -> GameState:
        invasion_set = previous_state.turn_context.pending_invasion_commits | {
            InvasionCommit(ground_force_id=self.ground_force_id, to_planet_id=self.to_planet_id),
        }
        return replace(
            previous_state,
            turn_context=replace(
                previous_state.turn_context,
                pending_invasion_commits=invasion_set,
            ),
        )


class CommitGroundForceCommandRule(CommandRule[CommitGroundForceCommand], CandidateCommandProvider):
    def __repr__(self) -> str:
        return "CommitGroundForceCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.COMMIT_GROUND_FORCE}

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if state.turn_context.tactical_action_step != TacticalActionStep.INVASION:
            return []
        return [
            CommitGroundForceCommand(
                actor=state.active_player,
                command_type=CommandType.COMMIT_GROUND_FORCE,
                ground_force_id=i,
                to_planet_id=j,
            )
            for i, j in itertools.product(
                [
                    unit.unit_id
                    for unit in state.get_units_in_system(state.get_active_system().id)
                    if (unit.owner_name == state.active_player) and unit.is_ground_force
                ],
                [planet.planet_id for planet in state.get_active_system().planets],
            )
        ]

    def validate_legality(
        self,
        state: GameState,
        command: CommitGroundForceCommand,
    ) -> ValidationResult:
        if state.active_player != command.actor:
            return ValidationResult(
                is_valid=False,
                info="Only active player can commit ground forces.",
            )
        if state.turn_context.tactical_action_step != TacticalActionStep.INVASION:
            return ValidationResult(
                is_valid=False,
                info="Can only commit ground forces during invasion step of tactical action.",
            )
        ground_force = state.get_ground_force_from_id(command.ground_force_id)
        if ground_force.owner_name != command.actor.name:
            return ValidationResult(
                is_valid=False,
                info="Can only commit ground forces you control.",
            )
        if ground_force.system_id != state.get_active_system().id:
            return ValidationResult(
                is_valid=False,
                info="Ground force is not in the active system.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: CommitGroundForceCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [
            AddInvasionCommitToPendingEvent(
                ground_force_id=command.ground_force_id,
                to_planet_id=command.to_planet_id,
            ),
        ]


class ResolvePendingInvasionCommitsEvent(Event):
    def __repr__(self) -> str:
        return "ResolvePendingInvasionCommitsEvent"

    def apply(self, previous_state: GameState) -> GameState:
        new_state = previous_state
        committed_units = set[GroundForce]()
        for commit in previous_state.turn_context.pending_invasion_commits:
            ground_force = new_state.get_ground_force_from_id(commit.ground_force_id)
            ground_force = ground_force.set_planet_id(commit.to_planet_id)
            committed_units.add(ground_force)
        committed_unit_ids = {unit.unit_id for unit in committed_units}
        return replace(
            new_state,
            units=frozenset(
                {unit for unit in previous_state.units if unit.unit_id not in committed_unit_ids}
                | committed_units,
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

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return [ResolvePendingInvasionCommitsEvent()]


class AdvanceToProductionStepEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolvePendingInvasionCommitsEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        # TODO: Space cannon defense, ground combat, etc.
        del state, event
        return [AdvanceToProductionStepEvent()]


def get_command_rules() -> list[CommandRule[CommitGroundForceCommand] | CommandRule[Command]]:
    return [
        ResolveBombardmentCommandRule(),
        PassBombardmentCommandRule(),
        EndInvasionCommandRule(),
        CommitGroundForceCommandRule(),
    ]


def get_event_rules() -> list[EventRule]:
    return [
        OpenBombardmentWindowEventRule(),
        CloseBombardmentWindowEventRule(),
        AdvanceToProductionStepEventRule(),
    ]
