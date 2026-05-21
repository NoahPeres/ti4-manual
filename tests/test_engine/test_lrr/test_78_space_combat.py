from typing import TYPE_CHECKING

import pytest

from src.engine.core.command import Command, CommandRule, CommandType, ValidationResult
from src.engine.core.game_engine import CommandResult
from src.engine.core.game_state import (
    GameState,
    HexCoord,
    SpaceCombatStep,
    System,
    TacticalActionStep,
    Window,
)
from src.engine.tokens import CommandToken
from src.engine.units.units import ShipKind, Unit, make_unit_with_id
from tests.test_engine.test_lrr.common import (
    make_basic_session_from_players,
    make_player,
    make_tactical_action_movement_state,
    pass_space_cannon_window,
)

if TYPE_CHECKING:
    from src.engine.core.event import Event

    pass


@pytest.mark.parametrize(
    "units,expected_tactical_action_step",
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


class AbilityAtStartOfSpaceCombat(CommandRule[Command]):
    def __repr__(self) -> str:
        return "AbilityAtStartOfSpaceCombat"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.ALWAYS_VALID}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> list[Event]:
        del command
        if state.window_context.is_window_active(Window.START_OF_SPACE_COMBAT):
            assert state.turn_context.tactical_action_step == TacticalActionStep.SPACE_COMBAT
            assert state.window_context.is_window_active(
                Window.START_OF_FIRST_ROUND_OF_SPACE_COMBAT,
            )
            assert state.window_context.is_window_active(Window.START_OF_SPACE_COMBAT)
            assert not state.window_context.is_window_active(
                Window.START_OF_A_ROUND_OF_SPACE_COMBAT,
            )
        return []


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
    session.engine.register_new_command_rule(AbilityAtStartOfSpaceCombat())
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    session.apply_command(
        command=Command(actor=player_a, command_type=CommandType.ALWAYS_VALID),
    )
    session.apply_command_result(
        CommandResult(new_state=session.current_state.close_all_windows(), success=True, events=[]),
    )
    assert session.current_state.turn_context.space_combat_context is not None
    assert (
        session.current_state.turn_context.space_combat_context.step
        == SpaceCombatStep.ANTI_FIGHTER_BARRAGE
    )
