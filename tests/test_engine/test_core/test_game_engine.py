from typing import TYPE_CHECKING

import pytest

from src.engine.core.command import Command, CommandRule, CommandType
from src.engine.core.event import Event
from src.engine.core.game_engine import (
    GameEngine,
    GameStateInvariant,
    InvariantViolationError,
)
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import GameState, Player
from src.engine.core.rules_engine import RulesEngine

from .common import FailingInvariant, TrivialEvent

if TYPE_CHECKING:
    from collections.abc import Sequence


class ChangePlayer(Event):
    def __init__(self, players: tuple[Player, ...]) -> None:
        self.payload: str = "change_player"
        self.players: tuple[Player, ...] = players

    def apply(self, previous_state: GameState) -> GameState:
        current_player: Player = previous_state.active_player
        current_index: int = self.players.index(current_player)
        new_player: Player = self.players[(current_index + 1) % len(self.players)]
        return GameState(players=previous_state.players, active_player=new_player)


class TrivialCommandRule(CommandRule):
    def __repr__(self) -> str:
        return "TrivialCommandRule"

    def validate_legality(self, state: GameState, command: Command):
        return command.command_type == CommandType.ALWAYS_VALID

    def derive_events(self, state: GameState, command: Command):
        return [TrivialEvent(payload="test")]


class EndTurn(CommandRule):
    def __repr__(self) -> str:
        return "EndTurn"

    def validate_legality(self, state: GameState, command: Command):
        return command.actor == state.active_player

    def derive_events(self, state: GameState, command: Command):
        if command.command_type == CommandType.END_TURN:
            return [ChangePlayer(players=state.players)]
        return []


class TrivialRulesEngine(RulesEngine):
    def __init__(self, command_rules: Sequence[CommandRule]) -> None:
        self.command_rules: Sequence[CommandRule] = command_rules
        self.event_rules = []


def _set_up_session(
    players: tuple[Player, ...],
    initial_player: Player = "TestPlayer",
    game_state_invariants: list[GameStateInvariant] | None = None,
    initial_state: GameState | None = None,
    command_rules: Sequence[CommandRule] | None = None,
) -> GameSession:
    if initial_state is None:
        initial_state = GameState(players=players, active_player=initial_player)
    if game_state_invariants is None:
        game_state_invariants = []
    if command_rules is None:
        command_rules = []
    engine = GameEngine(
        invariants=game_state_invariants,
        rules_engine=TrivialRulesEngine(command_rules=command_rules),
    )
    return GameSession(initial_state, engine=engine)


def test_when_command_invalid_no_event_applied() -> None:
    invalid_command = Command(actor="TestPlayer", command_type=CommandType.ALWAYS_INVALID)
    session: GameSession = _set_up_session(
        players=("TestPlayer",),
        initial_player="TestPlayer",
        command_rules=[TrivialCommandRule()],
    )
    new_state: GameState = session.apply_command(command=invalid_command)
    assert new_state == session.initial_state
    assert len(session.history) == 0  # Ensure history has not changed


def test_when_command_is_valid_we_apply_events() -> None:
    valid_command = Command(actor="TestPlayer", command_type=CommandType.ALWAYS_VALID)
    session: GameSession = _set_up_session(
        players=("TestPlayer",),
        initial_player="TestPlayer",
        command_rules=[TrivialCommandRule()],
    )
    _: GameState = session.apply_command(command=valid_command)
    assert len(session.history) > 0  # Ensure history has changed, even if state hasn't


def test_end_turn_changes_active_player() -> None:
    session: GameSession = _set_up_session(
        players=("Player1", "Player2"),
        initial_player="Player1",
        command_rules=[EndTurn()],
    )
    end_turn_command = Command(actor="Player1", command_type=CommandType.END_TURN)
    new_state: GameState = session.apply_command(command=end_turn_command)
    assert new_state.active_player == "Player2"


def test_invariant_violation_prevents_state_change() -> None:
    end_turn_command = Command(actor="Player1", command_type=CommandType.END_TURN)
    session: GameSession = _set_up_session(
        players=("Player1", "Player2"),
        initial_player="Player1",
        game_state_invariants=[FailingInvariant()],
        command_rules=[EndTurn()],
    )
    with pytest.raises(expected_exception=InvariantViolationError):
        _: GameState = session.apply_command(command=end_turn_command)


def test_undo_end_turn() -> None:
    session: GameSession = _set_up_session(
        players=("Player1", "Player2"),
        initial_player="Player1",
        command_rules=[EndTurn()],
    )
    end_turn_command = Command(actor="Player1", command_type=CommandType.END_TURN)
    state_after_end_turn: GameState = session.apply_command(command=end_turn_command)
    assert state_after_end_turn.active_player == "Player2"

    previous_state: GameState = session.undo()
    assert previous_state.active_player == "Player1"
    assert len(session.history) == 0  # Ensure history has been reverted


def test_undo_without_history_returns_initial_state() -> None:
    session: GameSession = _set_up_session(
        players=("Player1", "Player2"),
        initial_player="Player1",
        command_rules=[TrivialCommandRule()],
    )
    current_state: GameState = session.current_state
    assert current_state == session.initial_state

    state_after_undo = session.undo()
    assert state_after_undo == session.initial_state
