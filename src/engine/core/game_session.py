from src.engine.core.game_engine import GameEngine, CommandResult
from src.engine.core.game_state import GameState
from src.engine.core.command import Command


class GameSession:
    def __init__(self, initial_state: GameState, engine: GameEngine):
        self.initial_state: GameState = initial_state
        self.engine: GameEngine = engine
        self.history: list[CommandResult] = []

    @property
    def current_state(self) -> GameState:
        return self.history[-1].new_state if self.history else self.initial_state

    def apply_command(self, command: Command) -> GameState:
        command_result: CommandResult = self.engine.apply_command(
            state=self.current_state, command=command
        )
        if command_result.success:
            new_state: GameState = command_result.new_state
            self.history.append(command_result)
            return new_state
        return self.current_state

    def undo(self) -> GameState:
        raise NotImplementedError("Undo functionality is not yet implemented.")
