from dataclasses import FrozenInstanceError, dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.command import Command
    from src.engine.core.event import Event
    from src.engine.core.game_state import GameState
    from src.engine.core.rules_engine import RulesEngine


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

    def apply_command(self, state: GameState, command: Command) -> CommandResult:
        # Validate command legality
        for rule in self.rules_engine.command_rules:
            if not rule.validate_legality(state, command):
                return CommandResult(
                    new_state=state,
                    success=False,
                    events=[],
                    info=f"Command invalid: {command} because of rule {rule}",
                )
        # Derive events from command
        new_state: GameState = state
        events: list[Event] = []
        resolved_events: list[Event] = []
        for rule in self.rules_engine.command_rules:
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
