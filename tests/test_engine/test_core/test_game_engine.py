from src.engine.core.command import Command
from src.engine.core.event import Event
from src.engine.core.game_state import GameState, Player
from src.engine.core.game_session import GameSession
from src.engine.core.game_engine import GameEngine, GameStateInvariant


class TrivialEvent(Event):
    def __init__(self, payload: str):
        self.payload: str = payload

    def apply(self, previous_state):
        # For testing purposes, we just return the previous state unchanged
        return previous_state


class ChangePlayer(Event):
    def __init__(self, players: tuple[Player, ...]):
        self.payload: str = "change_player"
        self.players: tuple[Player, ...] = players

    def apply(self, previous_state: GameState) -> GameState:
        current_player: Player = previous_state.active_player
        current_index: int = self.players.index(current_player)
        new_player: Player = self.players[(current_index + 1) % len(self.players)]
        new_state = GameState(players=previous_state.players, active_player=new_player)
        return new_state


class InvalidCommand(Command):
    def __init__(self, actor: Player = "TestPlayer"):
        self.actor: str = actor

    def pre_validate(self, state: GameState):
        return False

    def derive_events(self, state: GameState):
        return [TrivialEvent(payload="test")]


class ValidCommand(Command):
    def __init__(self, actor: Player = "TestPlayer"):
        self.actor: str = actor

    def pre_validate(self, state: GameState):
        return True

    def derive_events(self, state: GameState):
        return [TrivialEvent(payload="test")]


class EndTurn(Command):
    def __init__(self, actor: Player = "TestPlayer"):
        self.actor: str = actor

    def pre_validate(self, state: GameState):
        return True

    def derive_events(self, state: GameState):
        return [ChangePlayer(players=state.players)]


def _set_up_session(
    players: tuple[Player, ...],
    initial_player: Player = "TestPlayer",
    game_state_invariants: list[GameStateInvariant] | None = None,
    initial_state: GameState | None = None,
) -> GameSession:
    if initial_state is None:
        initial_state = GameState(players=players, active_player=initial_player)
    if game_state_invariants is None:
        game_state_invariants = []
    engine = GameEngine(invariants=game_state_invariants)
    session = GameSession(initial_state, engine=engine)
    return session


def test_when_command_invalid_no_event_applied():
    invalid_command = InvalidCommand()
    session: GameSession = _set_up_session(
        players=("TestPlayer",), initial_player="TestPlayer"
    )
    new_state: GameState = session.apply_command(command=invalid_command)
    assert new_state == session.initial_state
    assert len(session.history) == 0  # Ensure history has not changed


def test_when_command_is_valid_we_apply_events():
    valid_command = ValidCommand()
    session: GameSession = _set_up_session(
        players=("TestPlayer",), initial_player="TestPlayer"
    )
    _: GameState = session.apply_command(command=valid_command)
    assert len(session.history) > 0  # Ensure history has changed, even if state hasn't


def test_end_turn_changes_active_player():
    session: GameSession = _set_up_session(
        players=("Player1", "Player2"), initial_player="Player1"
    )
    end_turn_command = EndTurn(actor="Player1")
    new_state: GameState = session.apply_command(command=end_turn_command)
    assert new_state.active_player == "Player2"


def test_invariant_violation_prevents_state_change():
    class FailingInvariant(GameStateInvariant):
        def check(self, state: GameState) -> bool:
            return False  # Always fails

    end_turn_command = EndTurn(actor="Player1")
    session: GameSession = _set_up_session(
        players=("Player1", "Player2"),
        initial_player="Player1",
        game_state_invariants=[FailingInvariant()],
    )
    new_state: GameState = session.apply_command(command=end_turn_command)
    assert (
        new_state == session.initial_state
    )  # State should not change due to invariant failure
