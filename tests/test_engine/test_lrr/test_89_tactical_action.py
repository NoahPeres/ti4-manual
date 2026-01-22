from dataclasses import replace

from src.engine.actions.tactical_action import ActivateCommand
from src.engine.core.command import CommandType
from src.engine.core.game_state import System
from src.engine.core.player import CommandSheet, Player
from src.engine.strategy_cards import StrategyCard
from src.engine.tokens import CommandToken

from .common import make_basic_session_from_players


def test_89_1_active_player_must_activate_system_without_their_command_token() -> None:
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=0, strategy=0),
    )
    player_b = Player(
        name="B",
        strategy_cards=(StrategyCard(name="Diplomacy", initiative=2),),
        command_sheet=CommandSheet.make_from_int("B", tactic=1, fleet=0, strategy=0),
    )
    fresh_system = System(id=0, command_tokens=())
    previously_activated_system = System(
        id=0, command_tokens=(CommandToken(player_name=player_a.name),)
    )
    previously_activated_by_b = System(
        id=0, command_tokens=(CommandToken(player_name=player_b.name),)
    )
    session = make_basic_session_from_players(players=(player_a, player_b))
    assert session.engine.apply_command(
        state=replace(session.current_state, galaxy={fresh_system}),
        command=ActivateCommand(
            actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION, system_id=0
        ),
    ).success
    assert not session.engine.apply_command(
        state=replace(session.current_state, galaxy={previously_activated_system}),
        command=ActivateCommand(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
        ),
    ).success
    assert session.engine.apply_command(
        state=replace(session.current_state, galaxy={previously_activated_by_b}),
        command=ActivateCommand(
            actor=player_a,
            command_type=CommandType.INITIATE_TACTICAL_ACTION,
            system_id=0,
        ),
    ).success


def test_89_1_active_player_places_token_from_tactic_pool() -> None:
    player_a = Player(
        name="A",
        strategy_cards=(StrategyCard(name="Leadership", initiative=1),),
        command_sheet=CommandSheet.make_from_int("A", tactic=1, fleet=0, strategy=0),
    )
    session = make_basic_session_from_players(players=(player_a,))
    new_state = session.apply_command(
        command=ActivateCommand(
            actor=player_a, command_type=CommandType.INITIATE_TACTICAL_ACTION, system_id=0
        ),
    )
    activated_system = new_state.get_system(id=0)
    assert any(token.player_name == player_a.name for token in activated_system.command_tokens)
