from typing import TYPE_CHECKING

import pytest

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    EngineContext,
    ValidationResult,
)
from src.engine.core.event import Event
from src.engine.core.game_engine import (
    GameEngine,
    GameStateInvariant,
    InvariantViolationError,
)
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import Galaxy, GameState, Phase
from src.engine.core.player import Player
from src.engine.core.rules_engine import RulesEngine

from .common import FailingInvariant, TrivialEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

TEST_PLAYER = Player("TestPlayer")
PLAYER_1 = Player("Player1")
PLAYER_2 = Player("Player2")


class ChangePlayerEvent(Event):
    def __init__(self, players: tuple[Player, ...]) -> None:
        self.players: tuple[Player, ...] = players

    def __repr__(self) -> str:
        return f"ChangePlayerEvent:{self.players}"

    def apply(self, previous_state: GameState) -> GameState:
        current_player: Player = previous_state.active_player
        current_index: int = self.players.index(current_player)
        new_player: Player = self.players[(current_index + 1) % len(self.players)]
        return GameState(
            players=previous_state.players,
            active_player=new_player,
            phase=Phase.ACTION,
            galaxy=Galaxy(),
        )


class TrivialCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "TrivialCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return set(CommandType.all_command_types())

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state
        if command.command_type == CommandType.ALWAYS_VALID:
            return ValidationResult(is_valid=True)
        return ValidationResult(is_valid=False, info="Command is not always valid")

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return [TrivialEvent(payload="test")]


class EndTurn(CommandRule[Command]):
    def __repr__(self) -> str:
        return "EndTurn"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_TURN}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.is_active_player(command.actor) and command.command_type == CommandType.END_TURN:
            return ValidationResult(is_valid=True)
        return ValidationResult(is_valid=False, info="Only the active player can end their turn")

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del engine_context
        if command.command_type == CommandType.END_TURN:
            return [ChangePlayerEvent(players=state.players)]
        return []


class TrivialRulesEngine(RulesEngine):
    check_all_rules_have_implementations = False

    def __init__(self, command_rules: Sequence[CommandRule[Command]]) -> None:
        self.command_rules: Sequence[CommandRule[Command]] = command_rules
        self.event_rules = []
        self.allowed_commands_by_window = {}


def _set_up_session(
    players: tuple[Player, ...],
    initial_player: Player = TEST_PLAYER,
    game_state_invariants: list[GameStateInvariant] | None = None,
    initial_state: GameState | None = None,
    command_rules: Sequence[CommandRule[Command]] | None = None,
) -> GameSession:
    if initial_state is None:
        initial_state = GameState(
            players=players,
            active_player=initial_player,
            phase=Phase.ACTION,
            galaxy=Galaxy(),
        )
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
    invalid_command = Command(actor=TEST_PLAYER, command_type=CommandType.ALWAYS_INVALID)
    session: GameSession = _set_up_session(
        players=(TEST_PLAYER,),
        initial_player=TEST_PLAYER,
        command_rules=[TrivialCommandRule()],
    )
    new_state: GameState = session.apply_command(command=invalid_command)
    assert new_state == session.initial_state
    assert len(session.history) == 0  # Ensure history has not changed


def test_when_command_is_valid_we_apply_events() -> None:
    valid_command = Command(actor=TEST_PLAYER, command_type=CommandType.ALWAYS_VALID)
    session: GameSession = _set_up_session(
        players=(TEST_PLAYER,),
        initial_player=TEST_PLAYER,
        command_rules=[TrivialCommandRule()],
    )
    _: GameState = session.apply_command(command=valid_command)
    assert len(session.history) > 0  # Ensure history has changed, even if state hasn't


def test_end_turn_changes_active_player() -> None:
    session: GameSession = _set_up_session(
        players=(PLAYER_1, PLAYER_2),
        initial_player=PLAYER_1,
        command_rules=[EndTurn()],
    )
    end_turn_command = Command(actor=PLAYER_1, command_type=CommandType.END_TURN)
    new_state: GameState = session.apply_command(command=end_turn_command)
    assert new_state.active_player == PLAYER_2


def test_invariant_violation_prevents_state_change() -> None:
    end_turn_command = Command(actor=PLAYER_1, command_type=CommandType.END_TURN)
    session: GameSession = _set_up_session(
        players=(PLAYER_1, PLAYER_2),
        initial_player=PLAYER_1,
        game_state_invariants=[FailingInvariant()],
        command_rules=[EndTurn()],
    )
    with pytest.raises(expected_exception=InvariantViolationError):
        _: GameState = session.apply_command(command=end_turn_command)


def test_undo_end_turn() -> None:
    session: GameSession = _set_up_session(
        players=(PLAYER_1, PLAYER_2),
        initial_player=PLAYER_1,
        command_rules=[EndTurn()],
    )
    end_turn_command = Command(actor=PLAYER_1, command_type=CommandType.END_TURN)
    state_after_end_turn: GameState = session.apply_command(command=end_turn_command)
    assert state_after_end_turn.active_player == PLAYER_2

    previous_state: GameState = session.undo()
    assert previous_state.active_player == PLAYER_1
    assert len(session.history) == 0  # Ensure history has been reverted


def test_undo_without_history_returns_initial_state() -> None:
    session: GameSession = _set_up_session(
        players=(PLAYER_1, PLAYER_2),
        initial_player=PLAYER_1,
        command_rules=[TrivialCommandRule()],
    )
    current_state: GameState = session.current_state
    assert current_state == session.initial_state

    state_after_undo = session.undo()
    assert state_after_undo == session.initial_state
