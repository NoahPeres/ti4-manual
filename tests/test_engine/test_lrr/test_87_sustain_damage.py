import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.driver.game_driver import GameDriver
from src.engine.actions.movement import Window
from src.engine.core.command import CommandType
from src.engine.core.game_state import SpaceCombatStep
from src.engine.units.sustain_damage import SustainDamageCommand
from src.engine.units.units import ShipKind, make_unit_with_id
from tests.test_engine.test_lrr.common import (
    FixedDiceRoller,
    make_roll_dice_step_state,
)
from tests.test_engine.test_lrr.session_driver_policies import (
    DoNotRetreat,
    UseAFB,
    UseSustainDamage,
    make_dumb_space_combat_agent,
)


def test_87_sustain_damage_usable_before_assigning_hits() -> None:
    session = make_roll_dice_step_state(
        units=frozenset(
            {
                make_unit_with_id(
                    unit_id=0,
                    owner_name="A",
                    kind=ShipKind.DREADNOUGHT,
                    system_id=0,
                ),
                make_unit_with_id(
                    unit_id=1,
                    owner_name="B",
                    kind=ShipKind.DREADNOUGHT,
                    system_id=0,
                ),
            },
        ),
        dice_roller=FixedDiceRoller(value=10),
    )
    driver = GameDriver(policy=make_dumb_space_combat_agent([], select_first_legal_command=True))
    driver.play_until(
        session,
        stop_condition=lambda state: state.window_context.is_window_active(
            Window.BEFORE_ASSIGNING_HITS,
        ),
    )
    assert session.engine.apply_command(
        state=session.current_state,
        command=SustainDamageCommand(
            actor="A",
            command_type=CommandType.USE_SUSTAIN_DAMAGE,
            unit_id=0,
        ),
    ).success


always_use_sustain_if_able = make_dumb_space_combat_agent(
    additional_policies=[UseSustainDamage(), DoNotRetreat(), UseAFB()],
    select_first_legal_command=True,
)


@given(
    n_friendly_ships=st.integers(min_value=1, max_value=5),
    n_enemy_ships=st.integers(min_value=1, max_value=5),
)
def test_87_1_each_use_cancels_one_hit(n_friendly_ships: int, n_enemy_ships: int) -> None:
    session = make_roll_dice_step_state(
        units=frozenset(
            {
                make_unit_with_id(
                    unit_id=i,
                    owner_name="A",
                    kind=ShipKind.DREADNOUGHT,
                    system_id=0,
                )
                for i in range(n_friendly_ships)
            }
            | {
                make_unit_with_id(
                    unit_id=n_friendly_ships + j,
                    owner_name="B",
                    kind=ShipKind.DREADNOUGHT,
                    system_id=0,
                )
                for j in range(n_enemy_ships)
            },
        ),
        dice_roller=FixedDiceRoller(value=10),
    )
    driver = GameDriver(always_use_sustain_if_able)
    session = driver.play_until(
        session=session,
        stop_condition=lambda state: state.window_context.is_window_active(
            Window.END_OF_SPACE_COMBAT_ROUND,
        ),
    )
    n_destroyed_ships = max(n_enemy_ships - n_friendly_ships, 0)  # all ships score 1 hit
    n_remaining_ships = max(n_friendly_ships - n_destroyed_ships, 0)
    assert (
        len(session.current_state.get_ships_in_system(system_id=0, player_name="A"))
        == n_remaining_ships
    )


def test_87_2_3_damaged_unit_cannot_sustain_damage() -> None:
    session = make_roll_dice_step_state(
        units=frozenset(
            {
                make_unit_with_id(
                    unit_id=0,
                    owner_name="A",
                    kind=ShipKind.DREADNOUGHT,
                    system_id=0,
                ).set_is_damaged(is_damaged=True),
                make_unit_with_id(
                    unit_id=1,
                    owner_name="B",
                    kind=ShipKind.DREADNOUGHT,
                    system_id=0,
                ),
            },
        ),
        dice_roller=FixedDiceRoller(value=10),
    )
    driver = GameDriver(always_use_sustain_if_able)
    session = driver.play_until(
        session=session,
        stop_condition=lambda state: state.window_context.is_window_active(
            Window.BEFORE_ASSIGNING_HITS,
        ),
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=SustainDamageCommand(
            actor="A",
            command_type=CommandType.USE_SUSTAIN_DAMAGE,
            unit_id=0,
        ),
    ).success


@pytest.mark.skip(reason="Blocked by AFB implementation")
def test_87_4_can_only_sustain_if_hit_eligible() -> None:
    session = make_roll_dice_step_state(
        units=frozenset(
            {
                make_unit_with_id(
                    unit_id=0,
                    owner_name="A",
                    kind=ShipKind.DREADNOUGHT,
                    system_id=0,
                ),
                make_unit_with_id(
                    unit_id=0,
                    owner_name="A",
                    kind=ShipKind.FIGHTER,
                    system_id=0,
                ),
                make_unit_with_id(
                    unit_id=1,
                    owner_name="B",
                    kind=ShipKind.DESTROYER,
                    system_id=0,
                ),
            },
        ),
        dice_roller=FixedDiceRoller(value=10),  # AFB hits on a 9
    )
    driver = GameDriver(always_use_sustain_if_able)
    session = driver.play_until(
        session=session,
        stop_condition=lambda state: state.window_context.is_window_active(
            Window.BEFORE_ASSIGNING_HITS,
        ),
    )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANTI_FIGHTER_BARRAGE
    )
    assert not session.engine.apply_command(
        state=session.current_state,
        command=SustainDamageCommand(
            actor="A",
            command_type=CommandType.USE_SUSTAIN_DAMAGE,
            unit_id=0,
        ),
    ).success


@pytest.mark.skip(reason="No such abilities exist")
def test_87_5_cannot_cancel_destruction() -> None:
    pass


@pytest.mark.skip(reason="Faction specific")
def test_87_6_non_euclidean_shielding() -> None:
    pass
