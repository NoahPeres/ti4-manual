from collections.abc import Sequence
import pytest

from src.engine.core.command import Command, CommandType
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import GameState, Player
from src.engine.strategy_cards import StrategyCard
from src.engine.core.event import EventRule, Event

from .common import get_default_game_engine


def make_basic_session_from_players(players: tuple[Player, ...]) -> GameSession:
    engine = get_default_game_engine()
    return GameSession(
        initial_state=GameState(
            players=players,
            active_player=players[0],
        ),
        engine=engine,
    )


def test_3_1_player_may_perform_one_action() -> None:
    player_a = Player(name="PlayerA")
    session = make_basic_session_from_players(players=(player_a,))

    # try to end turn having taken no action
    try_to_end_turn = session.engine.apply_command(
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
    try_to_take_second_action = session.engine.apply_command(
        state=session.current_state,
        command=Command(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
        ),
    )
    assert not try_to_take_second_action.success


def test_3_2_players_can_pass_then_end_turn() -> None:
    player_a = Player(
        name="A", strategy_cards=(StrategyCard(name="XXX", initiative=1, is_ready=False),)
    )
    player_b = Player(name="B", strategy_cards=(StrategyCard(name="YYY", initiative=2),))
    session = make_basic_session_from_players(players=(player_a, player_b))

    class OnEndTurnEvent(Event):
        payload = "EndTurnTriggeredAbility"

        def apply(self, previous_state: GameState) -> GameState:
            return previous_state

    class EndTurnTrigger(EventRule):
        def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
            if event.payload == "PassAction":
                return [OnEndTurnEvent()]
            else:
                return []

    session.engine.rules_engine.event_rules = [
        *session.engine.rules_engine.event_rules,
        EndTurnTrigger(),
    ]

    new_state: GameState = session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.PASS_ACTION)
    )
    new_player_a: Player = next(player for player in new_state.players if player.name == "A")
    assert new_player_a.has_passed
    assert any(event.payload == "EndTurnTriggeredAbility" for event in session.history[-1].events)
    assert new_state.active_player == player_b


def test_3_3_passed_players_cannot_perform_additional_actions() -> None:
    player_a = Player(
        name="A", strategy_cards=(StrategyCard(name="XXX", initiative=1, is_ready=False),)
    )
    player_b = Player(name="B", strategy_cards=(StrategyCard(name="YYY", initiative=2),))
    session = make_basic_session_from_players(players=(player_a, player_b))

    new_state: GameState = session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.PASS_ACTION)
    )
    assert player_a not in new_state.initiative_order_unpassed

    try_another_action = session.engine.apply_command(
        state=new_state,
        command=Command(actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION),
    )
    assert not try_another_action.success


@pytest.mark.skip(reason="Blocked by other implementation")
def test_3_3_a_while_passing_can_still_resolve_transactions_and_abilities() -> None:
    pass


@pytest.mark.skip(reason="Blocked by other implementation")
def test_3_3_b_passed_players_can_do_secondary() -> None:
    pass


def test_3_3_c_player_can_perform_multiple_consecutive_actions() -> None:
    player_a = Player(name="A", strategy_cards=(StrategyCard(name="Leadership", initiative=1),))
    player_b = Player(
        name="B",
        strategy_cards=(StrategyCard(name="Diplomacy", initiative=2, is_ready=False),),
        has_passed=True,
    )
    session = make_basic_session_from_players(players=(player_a, player_b))
    take_first_action = session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION)
    )
    assert take_first_action.has_taken_turn
    end_turn = session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_TURN)
    )
    assert end_turn.active_player == player_a
    assert session.engine.apply_command(
        state=end_turn,
        command=Command(actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION),
    ).success


def test_3_4_cannot_pass_until_strategic_action_taken() -> None:
    player_a = Player(name="A", strategy_cards=(StrategyCard(name="leadership", initiative=1),))
    session = make_basic_session_from_players(players=(player_a,))
    try_to_pass = session.engine.apply_command(
        state=session.initial_state,
        command=Command(actor=player_a, command_type=CommandType.PASS_ACTION),
    )
    assert not try_to_pass.success


def test_3_4_a_cannot_pass_until_all_strategy_cards_used() -> None:
    player_a = Player(
        name="A",
        strategy_cards=(
            StrategyCard(name="leadership", initiative=1),
            StrategyCard(name="Diplomacy", initiative=2, is_ready=False),
        ),
    )
    session = make_basic_session_from_players(players=(player_a,))
    try_to_pass = session.engine.apply_command(
        state=session.initial_state,
        command=Command(actor=player_a, command_type=CommandType.PASS_ACTION),
    )
    assert not try_to_pass.success
