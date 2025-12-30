from src.engine.core.command import Command, CommandType
from src.engine.core.game_engine import GameEngine
from src.engine.core.game_state import GameState, Player, TurnContext
from src.engine.core.ti4_rules_engine import TI4RulesEngine

TEST_PLAYER = Player("TestPlayer")
ANOTHER_PLAYER = Player("AnotherPlayer")
ENGINE = GameEngine(rules_engine=TI4RulesEngine())


def test_end_turn_command_changes_active_player() -> None:
    result = ENGINE.apply_command(
        state=GameState(
            players=(TEST_PLAYER, ANOTHER_PLAYER),
            active_player=TEST_PLAYER,
            turn_context=TurnContext(has_taken_action=True),
        ),
        command=Command(actor=TEST_PLAYER, command_type=CommandType.END_TURN),
    )

    assert result.new_state.active_player == ANOTHER_PLAYER
    assert result.success is True
    assert len(result.events) > 0  # Ensure some events were generated


def test_only_active_player_can_end_turn() -> None:
    result = ENGINE.apply_command(
        state=GameState(
            players=(TEST_PLAYER, ANOTHER_PLAYER),
            active_player=ANOTHER_PLAYER,
            turn_context=TurnContext(has_taken_action=True),
        ),
        command=Command(actor=TEST_PLAYER, command_type=CommandType.END_TURN),
    )

    assert result.new_state.active_player == ANOTHER_PLAYER  # Active player remains unchanged
    assert result.success is False
    assert len(result.events) == 0  # No events should be generated
