from dataclasses import replace
from itertools import product

import pytest

from src.engine.core.command import Command, CommandType
from src.engine.core.game_engine import CommandResult
from src.engine.core.game_state import (
    HexCoord,
    SpaceCombatStep,
    System,
    TacticalActionStep,
    Window,
)
from src.engine.core.game_session import GameSession
from src.engine.tokens import CommandToken
from src.engine.units.units import ShipKind, Unit, make_unit_with_id
from tests.test_engine.test_lrr.common import (
    make_basic_session_from_players,
    make_player,
    make_tactical_action_movement_state,
    pass_space_cannon_window,
)


@pytest.mark.parametrize(
    ("units", "expected_tactical_action_step"),
    [
        (frozenset[Unit](), TacticalActionStep.INVASION),
        (
            frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                },
            ),
            TacticalActionStep.INVASION,
        ),
        (
            frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                },
            ),
            TacticalActionStep.SPACE_COMBAT,
        ),
    ],
)
def test_78_1_space_combat_must_occur_iff_more_than_one_player_has_ships_after_space_cannon(
    *,
    units: frozenset[Unit],
    expected_tactical_action_step: TacticalActionStep,
) -> None:
    player_a = make_player(
        name="A",
    )
    player_b = make_player(
        name="B",
    )

    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=units,
            player_names=["A", "B"],
            systems=frozenset(
                {
                    System(
                        id=0,
                        command_tokens=(CommandToken(player_name="A"),),
                        coordinates=HexCoord(x=0, y=0),
                    ),
                },
            ),
        ),
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    assert session.current_state.turn_context.tactical_action_step == expected_tactical_action_step


def test_78_2_ability_at_start_of_space_combat_occurs_before_afb() -> None:
    player_a = make_player(
        name="A",
    )
    player_b = make_player(
        name="B",
    )

    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                },
            ),
            player_names=["A", "B"],
            systems=frozenset(
                {
                    System(
                        id=0,
                        command_tokens=(CommandToken(player_name="A"),),
                        coordinates=HexCoord(x=0, y=0),
                    ),
                },
            ),
        ),
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    for player in (player_a, player_b):
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_START_OF_COMBAT_ROUND),
        )
    assert session.current_state.turn_context.space_combat_context is not None
    assert (
        session.current_state.turn_context.space_combat_context.step
        == SpaceCombatStep.ANTI_FIGHTER_BARRAGE
    )


def test_78_2_a_start_of_first_combat_round_and_start_of_combat_are_the_same_window() -> None:
    player_a = make_player(
        name="A",
    )
    player_b = make_player(
        name="B",
    )

    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                },
            ),
        ),
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    assert session.current_state.window_context.is_window_active(
        Window.START_OF_FIRST_ROUND_OF_SPACE_COMBAT,
    )
    assert session.current_state.window_context.is_window_active(Window.START_OF_SPACE_COMBAT)


def make_start_of_space_combat_state() -> GameSession:
    player_a = make_player(
        name="A",
    )
    player_b = make_player(
        name="B",
    )

    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=frozenset(
                {
                    make_unit_with_id(
                        unit_id=1,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                    make_unit_with_id(
                        unit_id=2,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=0,
                    ),
                },
            ),
            player_names=["A", "B"],
        ),
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    return session


def test_78_2_b_end_of_last_combat_round_and_end_of_combat_are_the_same_window() -> None:
    session = make_start_of_space_combat_state()
    player_a = session.current_state.get_player("A")
    assert session.current_state.turn_context.space_combat_context is not None
    assigned_hits = replace(
        session.current_state.turn_context.space_combat_context,
        assigned_hits=frozenset({2}),
        step=SpaceCombatStep.ASSIGN_HITS,
    )
    session.apply_command_result(
        CommandResult(
            new_state=replace(
                session.current_state.close_all_windows(),
                turn_context=replace(
                    session.current_state.turn_context,
                    space_combat_context=assigned_hits,
                ),
            ),
            success=True,
            events=[],
        ),
    )
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_ASSIGN_HITS),
    )
    assert len(session.current_state.get_ships_in_system(0)) == 1
    assert session.current_state.window_context.is_window_active(
        Window.END_OF_SPACE_COMBAT_ROUND,
    )
    assert session.current_state.window_context.is_window_active(Window.END_OF_SPACE_COMBAT)


def test_78_3_players_may_roll_afb_iff_the_first_round_of_combat() -> None:
    session = make_start_of_space_combat_state()
    player_a = session.current_state.get_player("A")
    player_b = session.current_state.get_player("B")
    assert (
        session.current_state.turn_context.tactical_action_step == TacticalActionStep.SPACE_COMBAT
    )
    assert session.current_state.turn_context.space_combat_context is not None
    assert session.current_state.turn_context.space_combat_context.round_number == 1
    assert (
        session.current_state.turn_context.space_combat_context.step
        == SpaceCombatStep.ANTI_FIGHTER_BARRAGE
    )
    for player in (player_a, player_b):
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_START_OF_COMBAT_ROUND),
        )

    for player, command_type in product(
        (player_a, player_b),
        (CommandType.USE_ANTI_FIGHTER_BARRAGE, CommandType.PASS_ANTI_FIGHTER_BARRAGE),
    ):
        assert session.engine.apply_command(
            state=session.current_state,
            command=Command(actor=player, command_type=command_type),
        ).success
