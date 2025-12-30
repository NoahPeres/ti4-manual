from src.engine.core.command import Command, CommandType
from src.engine.core.game_engine import GameEngine
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import GameState, Player, TurnContext
from src.engine.core.ti4_rules_engine import TI4RulesEngine


def test_3_1_player_may_perform_one_action() -> None:
    player_a = Player(name="PlayerA")
    initial_state = GameState(
        players=(player_a,),
        active_player=player_a,
    )
    engine = GameEngine(rules_engine=TI4RulesEngine())
    session = GameSession(
        initial_state=initial_state,
        engine=engine,
    )

    # try to end turn having taken no action
    try_to_end_turn = engine.apply_command(
        state=session.current_state,
        command=Command(
            actor=player_a,
            command_type=CommandType.END_TURN,
        ),
    )
    assert not try_to_end_turn.success

    # take a tactical action
    session.apply_command(
        Command(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
        )
    )
    assert session.history[-1].success
    try_to_take_second_action = engine.apply_command(
        state=session.current_state,
        command=Command(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
        ),
    )
    assert not try_to_take_second_action.success


def test_3_2_players_can_pass_then_end_turn() -> None:
    player_a = Player(name="A")
    player_b = Player(name="B")
    engine = GameEngine(rules_engine=TI4RulesEngine())
    session = GameSession(
        initial_state=GameState(
            players=(player_a, player_b),
            active_player=player_a,
            turn_context=TurnContext(has_taken_action=False),
        ),
        engine=engine,
    )

    new_state: GameState = session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.PASS_ACTION)
    )
    assert new_state.active_player.has_passed
    turn_ended = session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_TURN)
    )
    assert turn_ended.active_player == player_b
