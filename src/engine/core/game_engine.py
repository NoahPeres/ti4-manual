import logging
from dataclasses import FrozenInstanceError, dataclass
from typing import TYPE_CHECKING, Protocol

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    EngineContext,
)
from src.engine.core.dice_roller import DiceRoller, UniformDiceRoller
from src.engine.core.game_state import ComponentNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.event import Event, EventRule
    from src.engine.core.game_state import GameState
    from src.engine.core.rules_engine import RulesEngine

logger = logging.getLogger(__name__)


class GameStateInvariant(Protocol):
    description: str

    def check(self, state: GameState) -> bool: ...


class InvariantViolationError(RuntimeError):
    pass


class IllegalStateMutationError(RuntimeError):
    def __init__(self, cause: str) -> None:
        super().__init__(f"Illegal state mutation: {cause}")


@dataclass(frozen=True)
class CommandResult:
    new_state: GameState
    success: bool
    events: Sequence[Event]
    info: str = ""


class GameEngine:
    def __init__(
        self,
        rules_engine: RulesEngine,
        invariants: Sequence[GameStateInvariant] | None = None,
        dice_roller: DiceRoller | None = None,
    ) -> None:
        self.rules_engine: RulesEngine = rules_engine
        self.invariants: Sequence[GameStateInvariant] = invariants if invariants is not None else []
        self.dice_roller: DiceRoller = (
            dice_roller if dice_roller is not None else UniformDiceRoller()
        )

        self._command_type_to_rules: dict[CommandType, list[CommandRule[Command]]] = {}
        self._event_type_to_rules: dict[type[Event], list[EventRule]] = {}
        for command_rule in self.rules_engine.command_rules:
            self.register_new_command_rule(command_rule)
        for event_rule in self.rules_engine.event_rules:
            self.register_new_event_rule(event_rule)

        unimplemented = self.get_unimplemented_command_types()

        if unimplemented and rules_engine.check_all_rules_have_implementations:
            msg = f"Unimplemented command types: {sorted(str(cmd) for cmd in unimplemented)}"
            raise NotImplementedError(msg)

    def register_new_command_rule(self, rule: CommandRule[Command]) -> None:
        self.rules_engine.command_rules = [*self.rules_engine.command_rules, rule]
        for cmd_type in rule.handles_command_types():
            self._command_type_to_rules.setdefault(cmd_type, []).append(rule)

    def register_new_event_rule(self, rule: EventRule) -> None:
        self.rules_engine.event_rules = [*self.rules_engine.event_rules, rule]
        for event_type in rule.handles_event_types():
            self._event_type_to_rules.setdefault(event_type, []).append(rule)

    def get_implemented_command_types(self) -> set[CommandType]:
        """Return the set of CommandTypes that have at least one rule."""
        return set(self._command_type_to_rules.keys()) | {
            CommandType.ALWAYS_VALID,
            CommandType.ALWAYS_INVALID,
            # These are vacuously 'implemented'
        }

    def get_unimplemented_command_types(self) -> set[CommandType]:
        """Return the set of CommandTypes with no rules."""

        all_types = set(CommandType.all_command_types())
        return all_types - self.get_implemented_command_types()

    def _is_command_legal(self, state: GameState, command: Command) -> tuple[bool, str]:
        if command.command_type == CommandType.ALWAYS_INVALID:
            return False, "Command invalid: ALWAYS_INVALID"

        if command.command_type not in self.get_implemented_command_types():
            return False, f"Command type not implemented: {command.command_type}"

        for window in state.window_context.active_windows:
            if command.command_type not in self.rules_engine.allowed_commands_by_window.get(
                window,
                (),
            ):
                return False, f"Command {command} may not be made during window {window.value}"

        for rule in self._command_type_to_rules.get(command.command_type, []):
            try:
                validation_result = rule.validate_legality(state, command)
            except ComponentNotFoundError as e:
                return False, f"Error occurred while validating command {command}: {e}"
            if not validation_result.is_valid:
                reason = validation_result.info or "<no reason provided>"
                return False, f"Command invalid: {command}. Reason: {reason}"

        return True, ""

    def apply_command(self, state: GameState, command: Command) -> CommandResult:
        is_legal, reason = self._is_command_legal(state=state, command=command)
        if not is_legal:
            return CommandResult(new_state=state, success=False, events=[], info=reason)

        # Derive events from command
        new_state: GameState = state
        events: list[Event] = []
        resolved_events: list[Event] = []
        for rule in self._command_type_to_rules.get(command.command_type, []):
            events += rule.derive_events(
                state,
                command,
                EngineContext(dice_roller=self.dice_roller),
            )

        while events:
            event: Event = events.pop(0)
            # NOTE: Events are resolved Depth-first by convention:
            # newly spawned events are prepended to the container.
            new_state, events = self._resolve_single_event(
                event=event,
                previous_state=new_state,
                resolved_events=resolved_events,
                pending_events=events,
            )

        self.check_invariants(new_state)
        if len(resolved_events) == 0:
            msg = f"Command {command.command_type} resolved no events"
            raise RuntimeError(msg)
        return CommandResult(new_state=new_state, success=True, events=resolved_events)

    def check_invariants(self, state: GameState) -> None:
        failed_invariants: list[GameStateInvariant] = [
            inv for inv in self.invariants if not inv.check(state=state)
        ]
        if failed_invariants:
            raise InvariantViolationError(
                "Game state invariants violated: "
                + ", ".join(inv.description for inv in failed_invariants),
            )

    def _resolve_single_event(
        self,
        event: Event,
        previous_state: GameState,
        resolved_events: list[Event],
        pending_events: list[Event],
    ) -> tuple[GameState, list[Event]]:
        try:
            new_state: GameState = event.apply(previous_state=previous_state)
        except FrozenInstanceError as e:
            raise IllegalStateMutationError(repr(event)) from e
        resolved_events.append(event)
        relevant_event_rules = self._event_type_to_rules.get(type(event), [])
        for rule in relevant_event_rules:
            try:
                new_events: Sequence[Event] = rule.on_event(state=new_state, event=event)
            except FrozenInstanceError as e:
                raise IllegalStateMutationError(repr(event)) from e
            pending_events = list(new_events) + pending_events
        return new_state, pending_events

    def get_legal_commands(
        self,
        state: GameState,
    ) -> list[Command]:
        legal: list[Command] = []

        for rule in self.rules_engine.command_rules:
            try:
                candidates = rule.candidate_commands(state)
            except ComponentNotFoundError:
                continue  # If a component is missing, we can't generate candidates for this rule
            for command in candidates:
                if command in legal:
                    continue

                is_legal, _ = self._is_command_legal(state=state, command=command)
                if is_legal:
                    legal.append(command)

        if len(legal) == 0:
            msg = f"No legal commands found. Active windows: {state.window_context.active_windows}"
            raise RuntimeError(msg)
        return legal
