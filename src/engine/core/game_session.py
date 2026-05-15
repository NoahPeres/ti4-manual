from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.engine.core.command import Command
    from src.engine.core.game_engine import CommandResult, GameEngine
    from src.engine.core.game_state import GameState


class GameSession:
    def __init__(self, initial_state: GameState, engine: GameEngine) -> None:
        self.initial_state: GameState = initial_state
        self.engine: GameEngine = engine
        self.history: list[CommandResult] = []
        self.failure_history: list[CommandResult] = []

    @property
    def current_state(self) -> GameState:
        return self.history[-1].new_state if self.history else self.initial_state

    def apply_command(self, command: Command) -> GameState:
        command_result: CommandResult = self.engine.apply_command(
            state=self.current_state,
            command=command,
        )
        return self.apply_command_result(command_result)

    def apply_command_result(self, command_result: CommandResult) -> GameState:
        if command_result.success:
            self.history.append(command_result)
            return command_result.new_state
        self.failure_history.append(command_result)
        return self.current_state

    def undo(self) -> GameState:
        if not self.history:
            return self.current_state
        _: CommandResult = self.history.pop()
        return self.current_state
