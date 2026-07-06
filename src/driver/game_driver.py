from typing import TYPE_CHECKING, Iterable, Protocol

if TYPE_CHECKING:
    from src.engine.core.command import Command
    from src.engine.core.game_session import GameSession
    from src.engine.core.game_state import GameState


class CommandPolicy(Protocol):
    def select_command(self, state: GameState, legal_commands: Iterable[Command]) -> Command: ...


class OptionalCommandPolicy(Protocol):
    def select_command(
        self,
        state: GameState,
        legal_commands: Iterable[Command],
    ) -> Command | None: ...


class NoCommandChosenError(RuntimeError):
    def __init__(self, candidates: Iterable[Command]) -> None:
        self.candidates = candidates
        super().__init__(f"No command chosen from candidates: {candidates}")


class PriorityPolicy(CommandPolicy):
    def __init__(self, sub_policies: list[OptionalCommandPolicy]) -> None:
        self.sub_policies: list[OptionalCommandPolicy] = sub_policies
        self.command_priority: list[Command] = []

    def select_command(self, state: GameState, legal_commands: Iterable[Command]) -> Command:
        for sub_policy in self.sub_policies:
            command = sub_policy.select_command(state, legal_commands)
            if command is not None and command in legal_commands:
                return command
        raise NoCommandChosenError(legal_commands)


class GameStateQuery(Protocol):
    def __call__(self, state: GameState) -> bool: ...


class GameDriver:
    def __init__(self, policy: CommandPolicy) -> None:
        self.policy: CommandPolicy = policy

    def step(self, session: GameSession) -> GameSession:
        legal_commands = session.engine.get_legal_commands(session.current_state)
        chosen_command = self.policy.select_command(session.current_state, legal_commands)
        session.apply_command(chosen_command)
        return session

    def play_until(self, session: GameSession, stop_condition: GameStateQuery) -> GameSession:
        while not stop_condition(session.current_state):
            self.step(session)
        return session
