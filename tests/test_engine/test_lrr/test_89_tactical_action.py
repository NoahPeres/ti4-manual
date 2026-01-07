from dataclasses import replace

from src.engine.actions.tactical_action import ActivateCommand
from src.engine.core.command import CommandType
from src.engine.core.game_state import System
from src.engine.core.player import Player
from src.engine.strategy_cards import StrategyCard
from src.engine.tokens import CommandToken

from .common import make_basic_session_from_players


def test_89_1_active_player_must_activate_system_without_their_command_token() -> None:
    player_a = Player(name="A", strategy_cards=(StrategyCard(name="Leadership", initiative=1),))
    player_b = Player(name="B", strategy_cards=(StrategyCard(name="Diplomacy", initiative=2),))
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
