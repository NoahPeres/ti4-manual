from src.engine.core.command import Command, CommandRule, CommandType
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import GameState, TurnContext


class TacticalActionCompletedEvent(Event):
    payload: str = "TacticalActionCompletedEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return GameState(
            players=previous_state.players,
            active_player=previous_state.active_player,
            turn_context=TurnContext(
                has_taken_action=True, has_passed=previous_state.turn_context.has_passed
            ),
        )


class InitiateTacticalActionCommandRule(CommandRule):
    def __repr__(self) -> str:
        return "InitiateTacticalAction"

    def validate_legality(self, state: GameState, command: Command) -> bool:
        if command.command_type != CommandType.INITIATE_TACTICAL_ACTION:
            return True  # Not applicable
        return (state.active_player == command.actor) and not state.turn_context.has_taken_turn

    def derive_events(self, state: GameState, command: Command) -> list[Event]:
        # Placeholder event derivation; in a real implementation, this would create events
        # related to initiating a tactical action.
        return [TacticalActionCompletedEvent()]


def get_command_rules() -> list[CommandRule]:
    return [InitiateTacticalActionCommandRule()]


def get_event_rules() -> list[EventRule]:
    return []
