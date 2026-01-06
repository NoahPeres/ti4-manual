from collections.abc import Sequence
from dataclasses import dataclass

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.engine import tokens
from src.engine.core.command import Command, CommandType
from src.engine.core.game_engine import GameEngine
from src.engine.core.game_state import GameState, Phase, Player, TurnContext
from src.engine.core.ti4_rules_engine import TI4RulesEngine
from src.engine.strategy_cards import StrategyCard

ENGINE = GameEngine(rules_engine=TI4RulesEngine())


@dataclass(frozen=True)
class PlayerInitiative:
    name: str
    strategy_card: str
    initiative: int


def _make_player_with_strategy_card(name: str, strategy_card: StrategyCard) -> Player:
    return Player(name=name, strategy_cards=(strategy_card,))


@given(initiative=st.integers(min_value=1, max_value=8))
def test_48_1_initiative_defined_by_strategy_card(initiative: int) -> None:
    strategy_card = StrategyCard(name="XXX", initiative=initiative)
    player_a = _make_player_with_strategy_card(
        name="PlayerA",
        strategy_card=strategy_card,
    )
    assert player_a.initiative == strategy_card.initiative


@given(initiative=st.integers(min_value=1, max_value=8))
def test_48_1_a_player_with_naalu_token_has_initiative_0(initiative: int) -> None:
    strategy_card = StrategyCard(name="XXXXX", initiative=initiative)
    player_a = Player(
        name="PlayerA",
        strategy_cards=(strategy_card,),
        play_area=frozenset([tokens.TokenType.NAALU_ZERO]),
    )
    assert player_a.initiative == 0


@given(
    player_shuffle=st.permutations(
        [
            PlayerInitiative("PlayerA", "LEADERSHIP", 1),
            PlayerInitiative("PlayerB", "DIPLOMACY", 2),
            PlayerInitiative("PlayerC", "POLITICS", 3),
        ]
    )
)
def test_48_2_turn_respects_initiative_order(player_shuffle: Sequence[PlayerInitiative]) -> None:
    players: tuple[Player, ...] = tuple(
        _make_player_with_strategy_card(
            name=pi.name,
            strategy_card=StrategyCard(name=pi.strategy_card, initiative=pi.initiative),
        )
        for pi in player_shuffle
    )
    players_sorted_by_initiative = tuple(sorted(players, key=lambda p: p.initiative))
    player_1: Player = players[0]
    player_1_idx: int = players_sorted_by_initiative.index(player_1)
    player_2: Player = players_sorted_by_initiative[(player_1_idx + 1) % len(players)]
    player_3: Player = players_sorted_by_initiative[(player_1_idx + 2) % len(players)]
    initial_state = GameState(
        players=players,
        active_player=player_1,
        turn_context=TurnContext(has_taken_action=False),
        phase=Phase.ACTION,
    )
    # Player 1 ends turn
    player_1_action = ENGINE.apply_command(
        state=initial_state,
        command=Command(actor=player_1, command_type=CommandType.INITIATE_TACTICAL_ACTION),
    ).new_state
    state_after_p1: GameState = ENGINE.apply_command(
        state=player_1_action,
        command=Command(actor=player_1, command_type=CommandType.END_TURN),
    ).new_state

    assert state_after_p1.active_player == player_2
    # Player 2 ends turn
    player_2_action = ENGINE.apply_command(
        state=state_after_p1,
        command=Command(actor=player_2, command_type=CommandType.INITIATE_TACTICAL_ACTION),
    ).new_state
    state_after_p2: GameState = ENGINE.apply_command(
        state=player_2_action,
        command=Command(actor=player_2, command_type=CommandType.END_TURN),
    ).new_state
    assert state_after_p2.active_player == player_3
    # Player 3 ends turn
    player_3_action = ENGINE.apply_command(
        state=state_after_p2,
        command=Command(actor=player_3, command_type=CommandType.INITIATE_TACTICAL_ACTION),
    ).new_state
    state_after_p3: GameState = ENGINE.apply_command(
        state=player_3_action,
        command=Command(actor=player_3, command_type=CommandType.END_TURN),
    ).new_state
    assert state_after_p3.active_player == player_1  # Back to Player 1


@pytest.mark.skip(reason="Blocked by other implementation")
def test_48_2_b_only_strategy_phase_cards_determine_initiative_order() -> None:
    pass


def test_48_3_multiple_strategy_cards_choose_lowest_initiative() -> None:
    strategy_card_1 = StrategyCard(name="LEADERSHIP", initiative=1)
    strategy_card_2 = StrategyCard(name="DIPLOMACY", initiative=2)
    player_a = Player(
        name="PlayerA",
        strategy_cards=(strategy_card_1, strategy_card_2),
    )
    assert player_a.initiative == 1  # Lowest initiative among strategy cards
