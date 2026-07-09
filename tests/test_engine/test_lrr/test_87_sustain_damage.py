"""
87
SUSTAIN DAMAGE (UNIT ABILITY)
Some units have the “Sustain Damage” ability. Immediately before
a player assigns hits to their units, that player can use the “Sustain
Damage” ability of any of their units in the active system.
87.1 For each “Sustain Damage” ability that a player uses, one hit
produced by another player’s units is canceled. Then, each
unit using this ability is placed on its side to indicate that it is
damaged.
87.2 A damaged unit does not have reduced capabilities and is
functionally the same as an undamaged unit, except that it
cannot use the “Sustain Damage” ability.
87.3 A damaged unit cannot use the “Sustain Damage” ability until
it is repaired during the status phase or by another game effect.
87.4 A unit can use its “Sustain Damage” ability any time a hit is
produced against it. This includes hits produced during combat
and from unit abilities such as the “Space Cannon” ability.
a A unit can only use the “Sustain Damage” ability if it
is eligible to be hit. For example, a player cannot use a
dreadnought’s “Sustain Damage” ability to cancel a hit from
“Anti-Fighter Barrage.”
87.5 The “Sustain Damage” ability cannot be used to cancel an
effect that directly destroys a unit.
87.6 The Barony of Letnev’s “Non-Euclidean Shielding” faction
technology allows the Letnev player’s units with the “Sustain
Damage” ability to cancel up to two hits instead of one.

"""

from src.driver.game_driver import GameDriver
from src.engine.actions.movement import Window
from src.engine.core.command import CommandType
from src.engine.units.sustain_damage import SustainDamageCommand
from src.engine.units.units import ShipKind, make_unit_with_id
from tests.test_engine.test_lrr.common import (
    FixedDiceRoller,
    make_roll_dice_step_state,
)
from tests.test_engine.test_lrr.session_driver_policies import make_dumb_space_combat_agent


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
