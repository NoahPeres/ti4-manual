from src.engine.core.game_engine import GameEngine
from src.engine.core.game_state import GameState


class GameSession:
    def __init__(self, initial_state: GameState, engine: GameEngine):
        self.initial_state: GameState = initial_state
        self.engine: GameEngine = engine
        self.history: list[GameState] = [initial_state]

    @property
    def current_state(self) -> GameState:
        return self.history[-1]

    def apply_command(self, command) -> GameState:
        new_state: GameState = self.engine.apply_command(
            state=self.current_state, command=command
        )
        self.history.append(new_state)
        return new_state

    def undo(self) -> GameState:
        raise NotImplementedError("Undo functionality is not yet implemented.")
