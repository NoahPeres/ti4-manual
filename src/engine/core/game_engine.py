import logging
from dataclasses import FrozenInstanceError, dataclass
from typing import TYPE_CHECKING, Protocol

from src.engine.core.command import CommandRule, CommandType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.command import Command
    from src.engine.core.event import Event
    from src.engine.core.game_state import GameState
    from src.engine.core.rules_engine import RulesEngine

logger = logging.getLogger(__name__)


class GameStateInvariant(Protocol):
    description: str

    def check(self, state: GameState) -> bool: ...


class InvariantViolationError(RuntimeError):
    pass


class IllegalStateMutationError(RuntimeError):
    pass


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
    ) -> None:
        self.rules_engine: RulesEngine = rules_engine
        self.invariants: Sequence[GameStateInvariant] = invariants if invariants is not None else []

        self._command_type_to_rules: dict[CommandType, list[CommandRule[Command]]] = {}
        for rule in self.rules_engine.command_rules:
            for cmd_type in rule.handles_command_types():
                self._command_type_to_rules.setdefault(cmd_type, []).append(rule)

        unimplemented = self.get_unimplemented_command_types()

        if unimplemented:
            msg = f"Unimplemented command types: {sorted(str(cmd) for cmd in unimplemented)}"
            raise NotImplementedError(msg)

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

    def apply_command(self, state: GameState, command: Command) -> CommandResult:
        # Check if command type is implemented
        if command.command_type not in self.get_implemented_command_types():
            return CommandResult(
                new_state=state,
                success=False,
                events=[],
                info=f"Command type not implemented: {command.command_type}",
            )

        # Get relevant rules for this command type
        relevant_rules = self._command_type_to_rules.get(command.command_type, [])

        # Validate command legality with all relevant rules
        for rule in relevant_rules:
            validation_result = rule.validate_legality(state, command)
            if not validation_result.is_valid:
                reason = validation_result.info or "<no reason provided>"
                return CommandResult(
                    new_state=state,
                    success=False,
                    events=[],
                    info=f"Command invalid: {command}. Reason: {reason}",
                )
        # Derive events from command
        new_state: GameState = state
        events: list[Event] = []
        resolved_events: list[Event] = []
        for rule in relevant_rules:
            events += rule.derive_events(state, command)

        while events:
            event: Event = events.pop(0)
            try:
                new_state: GameState = event.apply(previous_state=new_state)
            except FrozenInstanceError as e:
                raise IllegalStateMutationError(
                    f"Illegal mutation of game state detected when applying event {event}: {e}"
                ) from e
            resolved_events.append(event)
            for rule in self.rules_engine.event_rules:
                try:
                    new_events: Sequence[Event] = rule.on_event(state=new_state, event=event)
                except FrozenInstanceError as e:
                    raise IllegalStateMutationError(
                        f"Illegal mutation of game state detected when processing event {event} "
                        f"with rule {rule}: {e}"
                    ) from e
                events: list[Event] = list(new_events) + events

        failed_invariants: list[GameStateInvariant] = [
            inv for inv in self.invariants if not inv.check(state=new_state)
        ]
        if failed_invariants:
            raise InvariantViolationError(
                "Game state invariants violated: "
                + ", ".join(inv.description for inv in failed_invariants),
            )
        return CommandResult(new_state=new_state, success=True, events=resolved_events)
