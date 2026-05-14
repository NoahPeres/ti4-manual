from copy import deepcopy
from typing import TYPE_CHECKING, Callable

import hypothesis.strategies as st
import pytest
from hypothesis import given

from src.engine.core.command import Command, CommandRule, CommandType, ValidationResult
from src.engine.core.event import Event, EventRule
from src.engine.core.game_engine import CommandResult, GameEngine, IllegalStateMutationError
from src.engine.core.game_state import GameState, Phase
from src.engine.core.player import Player
from src.engine.core.ti4_rules_engine import TI4RulesEngine

from .common import TrivialEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

PLAYERS = (Player(name="Player1"), Player(name="Player2"), Player(name="Player3"))
DETERMINISTIC_COMMANDS: list[CommandType] = [CommandType.END_TURN]


class MutatingEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return set()

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        state.active_player = "EVIL"  # type: ignore
        return []


class MutatingEvent(Event):
    def __repr__(self) -> str:
        return "MutatingEvent"

    def apply(self, previous_state: GameState) -> GameState:
        previous_state.active_player = "EVIL"  # type: ignore
        return previous_state


class MutatingCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "MutatingCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        # Test rule that intercepts all command types
        return set(CommandType.all_command_types())

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state, command
        return [TrivialEvent(payload="Does nothing"), MutatingEvent()]


@st.composite
def simple_game_state(draw: Callable[[st.SearchStrategy[Player]], Player]) -> GameState:
    players: tuple[Player, ...] = PLAYERS
    active_player: Player = draw(st.sampled_from(players))
    return GameState(
        players=players,
        active_player=active_player,
        phase=Phase.ACTION,
        galaxy=frozenset(),
    )


class CommandAlwaysFails(CommandRule[Command]):
    def __repr__(self) -> str:
        return "CommandAlwaysFails"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        # Test rule that intercepts all command types
        return set(CommandType.all_command_types())

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        return ValidationResult(is_valid=False, info="This command always fails")

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state, command
        return []


class CustomRulesEngine(TI4RulesEngine):
    def __init__(
        self,
        command_rules: Sequence[CommandRule[Command]],
        event_rules: Sequence[EventRule],
    ) -> None:
        super().__init__()
        self.command_rules: Sequence[CommandRule[Command]] = command_rules
        self.event_rules: Sequence[EventRule] = event_rules


@given(
    state=simple_game_state(),
    actor=st.sampled_from(PLAYERS),
    command_type=st.sampled_from(DETERMINISTIC_COMMANDS),
)
def test_engine_determinism(state: GameState, actor: Player, command_type: CommandType) -> None:
    state1: GameState = deepcopy(x=state)
    state2: GameState = deepcopy(x=state)
    engine = GameEngine(rules_engine=TI4RulesEngine())

    command = Command(actor=actor, command_type=command_type)

    r1: CommandResult = engine.apply_command(state=state1, command=command)
    r2: CommandResult = engine.apply_command(state=state2, command=command)

    assert all(
        type(event1) is type(event2) for event1, event2 in zip(r1.events, r2.events, strict=True)
    )
    assert r1.new_state == r2.new_state
    assert r1.success == r2.success


@given(
    state=simple_game_state(),
    actor=st.sampled_from(PLAYERS),
    command_type=st.sampled_from(DETERMINISTIC_COMMANDS),
)
def test_state_is_immutable_during_apply(
    state: GameState,
    actor: Player,
    command_type: CommandType,
):
    initial_state: GameState = deepcopy(x=state)
    snapshot: GameState = deepcopy(x=initial_state)

    engine = GameEngine(rules_engine=TI4RulesEngine())
    engine.apply_command(
        state=initial_state,
        command=Command(actor=actor, command_type=command_type),
    )

    assert initial_state == snapshot


@given(
    state=simple_game_state(),
    actor=st.sampled_from(PLAYERS),
    command_type=st.sampled_from(DETERMINISTIC_COMMANDS),
)
def test_rules_cannot_mutate_state(state: GameState, actor: Player, command_type: CommandType):
    initial_state: GameState = deepcopy(x=state)
    snapshot: GameState = deepcopy(x=initial_state)

    engine = GameEngine(
        rules_engine=CustomRulesEngine(
            command_rules=[MutatingCommandRule()],
            event_rules=[MutatingEventRule()],
        ),
    )

    with pytest.raises(expected_exception=IllegalStateMutationError):
        _: CommandResult = engine.apply_command(
            state=initial_state,
            command=Command(actor=actor, command_type=command_type),
        )
    assert initial_state == snapshot
