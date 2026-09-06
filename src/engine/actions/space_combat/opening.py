from typing import TYPE_CHECKING

from src.engine.actions.movement import EndMovementStepEvent, OpenWindowEvent
from src.engine.actions.space_combat.afb_and_retreat import ResetCombatToAnnounceRetreatStepEvent
from src.engine.actions.space_combat.shared import (
    END_OF_COMBAT_ROUND_WINDOWS,
    START_OF_COMBAT_ROUND_WINDOWS,
    active_ship_owners,
    get_active_system_id,
)
from src.engine.actions.tactical_action import (
    AdvanceToInvasionStepEvent,
    AdvanceToSpaceCombatStepEvent,
)
from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    EngineContext,
    ValidationResult,
    make_command_candidates_for_all_players,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, SpaceCombatContext, SpaceCombatStep, Window
from src.engine.core.windows import CloseWindowEvent

if TYPE_CHECKING:
    from collections.abc import Sequence


class StartSpaceCombatEvent(Event):
    def __repr__(self) -> str:
        return "StartSpaceCombatEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            space_combat_context=SpaceCombatContext(
                step=SpaceCombatStep.ANTI_FIGHTER_BARRAGE,
                round_number=1,
                attacker=previous_state.active_player.name,
                defender=previous_state.get_defender_in_system(
                    system_id=get_active_system_id(previous_state),
                ).name,
            ),
        )


class OpenStartOfSpaceCombatWindowEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {AdvanceToSpaceCombatStepEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event, state
        return [
            StartSpaceCombatEvent(),
        ] + [OpenWindowEvent(window=window) for window in START_OF_COMBAT_ROUND_WINDOWS]


class SkipSpaceCombatIfOnlyOnePlayerHasShips(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {EndMovementStepEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if len(active_ship_owners(state)) <= 1:
            return [AdvanceToInvasionStepEvent()]
        return [AdvanceToSpaceCombatStepEvent()]


class PassStartOfCombatWindowCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassStartOfCombatWindowCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_START_OF_COMBAT_ROUND}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.START_OF_SPACE_COMBAT_ROUND):
            return ValidationResult(
                is_valid=False,
                info="Can only pass at the start of a round of combat.",
            )
        if state.window_context.player_has_passed_on_window(
            player_name=command.actor,
            window=Window.START_OF_SPACE_COMBAT_ROUND,
        ):
            return ValidationResult(is_valid=False, info="You already passed on this window.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [PassStartOfCombatWindowEvent(player_name=command.actor)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=PassStartOfCombatWindowCommandRule,
        )


class PassEndOfCombatWindowCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassEndOfCombatWindowCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_END_OF_COMBAT_ROUND}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.END_OF_SPACE_COMBAT_ROUND):
            return ValidationResult(
                is_valid=False,
                info="Can only pass at the end of a round of combat.",
            )
        if state.window_context.player_has_passed_on_window(
            player_name=command.actor,
            window=Window.END_OF_SPACE_COMBAT_ROUND,
        ):
            return ValidationResult(is_valid=False, info="You already passed on this window.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [PassEndOfCombatWindowEvent(player_name=command.actor)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=PassEndOfCombatWindowCommandRule,
        )


class PassStartOfCombatWindowEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player = player_name

    def __repr__(self) -> str:
        return f"PassStartOfCombatWindowEvent:{self.player}"

    def apply(self, previous_state: GameState) -> GameState:
        active_state = previous_state
        for window in previous_state.window_context.active_windows:
            if window in START_OF_COMBAT_ROUND_WINDOWS:
                active_state = active_state.pass_on_window_for_player(
                    player_name=self.player,
                    window=window,
                )
        return active_state


class PassEndOfCombatWindowEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player_name = player_name

    def __repr__(self) -> str:
        return f"PassEndOfCombatWindowEvent:{self.player_name}"

    def apply(self, previous_state: GameState) -> GameState:
        active_state = previous_state
        for window in previous_state.window_context.active_windows:
            if window in END_OF_COMBAT_ROUND_WINDOWS:
                active_state = active_state.pass_on_window_for_player(
                    player_name=self.player_name,
                    window=window,
                )
        return active_state


class CloseStartOfSpaceCombatRoundWindowsEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {PassStartOfCombatWindowEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        events: list[Event] = []
        if all(
            state.window_context.player_has_passed_on_window(
                player.name,
                window=Window.START_OF_SPACE_COMBAT_ROUND,
            )
            for player in state.players
        ):
            events += [
                CloseWindowEvent(window=window)
                for window in state.window_context.active_windows
                if window in START_OF_COMBAT_ROUND_WINDOWS
            ]
            if state.turn_context.get_space_combat_context().round_number == 1:
                events += [OpenWindowEvent(window=Window.ANTI_FIGHTER_BARRAGE)]
        return events


class CloseEndOfSpaceCombatRoundWindowsEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {PassEndOfCombatWindowEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        events: list[Event] = []
        if all(
            state.window_context.player_has_passed_on_window(
                player.name,
                window=Window.END_OF_SPACE_COMBAT_ROUND,
            )
            for player in state.players
        ):
            events += [
                CloseWindowEvent(window=window)
                for window in state.window_context.active_windows
                if window in END_OF_COMBAT_ROUND_WINDOWS
            ]
            if len(active_ship_owners(state)) > 1:
                events += [
                    ResetCombatToAnnounceRetreatStepEvent(),
                    OpenWindowEvent(Window.START_OF_SPACE_COMBAT_ROUND),
                ]
        return events
