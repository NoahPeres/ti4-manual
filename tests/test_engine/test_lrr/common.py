from typing import TYPE_CHECKING

from src.engine.actions.movement import MoveShipCommand, TransportUnitCommand
from src.engine.actions.tactical_action import ActivateCommand
from src.engine.core.command import Command
from src.engine.core.dice_roller import DiceRoller
from src.engine.core.game_engine import CommandType, GameEngine
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import (
    Galaxy,
    GameState,
    Phase,
    SpaceCombatStep,
    TacticalActionStep,
    TurnContext,
)
from src.engine.core.invariants import make_all_invariants
from src.engine.core.player import CommandSheet, Player
from src.engine.core.system import HexCoord, Planet, System
from src.engine.core.ti4_rules_engine import TI4RulesEngine
from src.engine.tokens import CommandToken
from src.engine.units.units import ShipKind, Unit, make_unit_with_id

if TYPE_CHECKING:
    from src.engine.strategy_cards import StrategyCard


class InvalidPlayerCountError(ValueError):
    pass


def get_default_game_engine(dice_roller: DiceRoller | None = None) -> GameEngine:
    return GameEngine(
        rules_engine=TI4RulesEngine(),
        invariants=make_all_invariants(),
        dice_roller=dice_roller,
    )


def make_basic_session_from_players(
    players: tuple[Player, ...],
    initial_state: GameState | None = None,
    dice_roller: DiceRoller | None = None,
) -> GameSession:
    engine = get_default_game_engine(dice_roller=dice_roller)
    if len(players) == 0:
        raise InvalidPlayerCountError
    return GameSession(
        initial_state=initial_state
        or GameState(
            players=players,
            active_player_name=players[0].name,
            phase=Phase.ACTION,
            galaxy=Galaxy({System(id=0, command_tokens=()), System(id=1, command_tokens=())}),
        ),
        engine=engine,
    )


def make_player(
    name: str,
    strategy_cards: tuple[StrategyCard, ...] = (),
    command_sheet: CommandSheet | None = None,
    *,
    has_passed: bool = False,
) -> Player:
    return Player(
        name=name,
        strategy_cards=strategy_cards,
        command_sheet=command_sheet
        if command_sheet is not None
        else CommandSheet.make_from_int(name, tactic=3, fleet=3, strategy=2),
        has_passed=has_passed,
    )


def make_tactical_action_movement_state(
    active_system_id: int,
    units: frozenset[Unit] | None = None,
    players: tuple[Player, ...] | None = None,
    systems: Galaxy | None = None,
) -> GameState:
    if players is None:
        players = (
            make_player(
                "A",
                command_sheet=CommandSheet.make_from_int(
                    player_name="A",
                    tactic=2,
                    fleet=3,
                    strategy=2,
                    reinforcements=8,
                ),
            ),
        )

    if units is None:
        # Create default ship at system 0
        default_ship = make_unit_with_id(
            unit_id=0,
            owner_name=players[0].name,
            kind=ShipKind.DREADNOUGHT,
            system_id=0,
        )
        units = frozenset({default_ship})

    if systems is None:
        # Create systems with coordinates in a line
        systems = Galaxy(
            System(
                id=system_id,
                command_tokens=(CommandToken(players[0].name),)
                if system_id == active_system_id
                else (),
                coordinates=HexCoord(0, system_id),
            )
            for system_id in range(3)
        )

    return GameState(
        players=tuple(players),
        active_player_name=players[0].name,
        phase=Phase.ACTION,
        galaxy=systems,
        turn_context=TurnContext(
            has_initiated_action=True,
            tactical_action_step=TacticalActionStep.MOVEMENT,
            active_system_id=active_system_id,
        ),
        units=units,
    )


def grant_all_units_unique_ids(units: frozenset[Unit]) -> frozenset[Unit]:
    """Only for testing, ensure units have unique ids"""
    return frozenset(
        make_unit_with_id(
            unit_id=i,
            owner_name=unit.owner_name,
            kind=unit.kind,
            system_id=unit.system_id,
            planet_id=unit.cast_to_ground_force().planet_id if unit.is_ground_force else None,
        )
        for i, unit in enumerate(units)
    )


def build_game_state(
    players: tuple[Player, ...],
    active_player: Player | None = None,
    galaxy: Galaxy | None = None,
    turn_context: TurnContext | None = None,
    units: frozenset[Unit] | None = None,
) -> GameState:
    active_player = active_player or players[0]
    galaxy = galaxy or Galaxy(
        {
            System(id=0, command_tokens=(), coordinates=HexCoord(0, 0)),
            System(id=1, command_tokens=(), coordinates=HexCoord(0, 1)),
        },
    )
    turn_context = turn_context or TurnContext(
        has_initiated_action=True,
        tactical_action_step=TacticalActionStep.MOVEMENT,
        active_system_id=0,
    )
    return GameState(
        players=players,
        active_player_name=active_player.name,
        phase=Phase.ACTION,
        galaxy=galaxy,
        turn_context=turn_context,
        units=units or frozenset(),
    )


def make_session(
    players: tuple[Player, ...],
    active_player: Player | None = None,
    galaxy: Galaxy | None = None,
    turn_context: TurnContext | None = None,
    units: frozenset[Unit] | None = None,
) -> GameSession:
    return GameSession(
        initial_state=build_game_state(
            players=players,
            active_player=active_player,
            galaxy=galaxy,
            turn_context=turn_context,
            units=units,
        ),
        engine=get_default_game_engine(),
    )


def activate_command(actor: str, system_id: int) -> ActivateCommand:
    return ActivateCommand(
        actor=actor,
        command_type=CommandType.INITIATE_TACTICAL_ACTION,
        system_id=system_id,
    )


def move_command(
    actor: str,
    ship_id: int,
    to_system_id: int,
    transported_unit_ids: frozenset[int] = frozenset(),
) -> list[Command]:
    commands: list[Command] = [
        MoveShipCommand(
            actor=actor,
            command_type=CommandType.MOVE_SHIP,
            ship_id=ship_id,
            to_system_id=to_system_id,
        ),
    ]
    if len(transported_unit_ids) > 0:
        commands.extend(
            [
                TransportUnitCommand(
                    actor=actor,
                    command_type=CommandType.TRANSPORT_UNIT,
                    unit_id=unit_id,
                )
                for unit_id in transported_unit_ids
            ]
            + [Command(actor=actor, command_type=CommandType.PASS_TRANSPORT_UNIT)],
        )
    return commands


def make_movement_session(units: frozenset[Unit], galaxy: Galaxy | None = None) -> GameSession:
    players = (make_player("A"), make_player("B"))
    return make_session(
        players=players,
        active_player=players[0],
        turn_context=TurnContext(
            has_initiated_action=True,
            tactical_action_step=TacticalActionStep.MOVEMENT,
            active_system_id=1,
        ),
        units=units,
        galaxy=galaxy,
    )


def action_command(actor: str, command_type: CommandType) -> Command:
    return Command(actor=actor, command_type=command_type)


def end_movement(session: GameSession, state: GameState) -> GameState:
    return session.apply_command(
        command=action_command(state.active_player.name, CommandType.END_MOVEMENT),
    )


def resolve_space_cannon(session: GameSession, state: GameState) -> GameState:
    for player in state.players:
        assert state.active_system is not None
        if state.player_may_resolve_space_cannon_in_system(
            player_name=player.name,
            system_id=state.active_system.id,
        ):
            state = session.apply_command(
                command=action_command(player.name, CommandType.USE_SPACE_CANNON),
            )
    return state


def pass_space_cannon_window(session: GameSession, state: GameState) -> GameState:
    assert state.active_system is not None
    for player in state.players:
        state = session.apply_command(
            command=action_command(player.name, CommandType.PASS_SPACE_CANNON),
        )
    return state


def begin_invasion(session: GameSession, state: GameState) -> GameState:
    return pass_space_cannon_window(session, end_movement(session, state))


def pass_bombardment_window(session: GameSession, state: GameState) -> GameState:
    assert state.active_system is not None
    return session.apply_command(
        command=action_command(state.active_player.name, CommandType.PASS_BOMBARDMENT),
    )


CENTRE_RING_OF_SYSTEMS = Galaxy(
    {
        System(id=0, command_tokens=(), coordinates=HexCoord(0, 0), planets=frozenset({Planet(0)})),
        System(id=1, command_tokens=(), coordinates=HexCoord(1, 0)),
        System(id=2, command_tokens=(), coordinates=HexCoord(0, 1)),
        System(id=3, command_tokens=(), coordinates=HexCoord(-1, 0)),
        System(id=4, command_tokens=(), coordinates=HexCoord(0, -1)),
        System(id=5, command_tokens=(), coordinates=HexCoord(1, 1)),
        System(id=6, command_tokens=(), coordinates=HexCoord(-1, -1)),
    },
)


def make_centre_ring_with_player_token(player_name: str, system_id: int) -> Galaxy:
    """Create a centre ring galaxy with a command token for a player in a specific system."""
    return Galaxy(
        {
            System(
                id=system.id,
                command_tokens=(CommandToken(player_name=player_name),)
                if system.id == system_id
                else system.command_tokens,
                coordinates=system.coordinates,
                planets=system.planets,
            )
            for system in CENTRE_RING_OF_SYSTEMS
        },
    )


# Convenience constants for common configurations
CENTRE_RING_OF_SYSTEMS_WITH_PLAYER_A_TOKEN = make_centre_ring_with_player_token("A", 0)


class RepeatingDiceRoller(DiceRoller):
    """Dice roller that cycles through provided values."""

    def __init__(self, values: list[int]) -> None:
        self.values = values if values else [5]
        self.call_count = 0

    def roll(self, num_dice: int) -> list[int]:
        result: list[int] = []
        for _ in range(num_dice):
            result.append(self.values[self.call_count % len(self.values)])
            self.call_count += 1
        return result


def make_start_of_space_combat_state(
    initial_state: GameState | None = None,
    dice_roller: DiceRoller | None = None,
) -> GameSession:
    player_a = make_player(
        name="A",
    )
    player_b = make_player(
        name="B",
    )

    session = make_basic_session_from_players(
        players=(player_a, player_b),
        initial_state=initial_state
        or make_tactical_action_movement_state(
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
                    make_unit_with_id(
                        unit_id=3,
                        owner_name="A",
                        kind=ShipKind.DESTROYER,
                        system_id=1,
                    ),
                    make_unit_with_id(
                        unit_id=4,
                        owner_name="B",
                        kind=ShipKind.DESTROYER,
                        system_id=2,
                    ),
                },
            ),
            players=(player_a, player_b),
            systems=CENTRE_RING_OF_SYSTEMS,
        ),
        dice_roller=dice_roller,
    )
    session.apply_command(
        command=Command(actor=player_a.name, command_type=CommandType.END_MOVEMENT),
    )
    pass_space_cannon_window(session=session, state=session.current_state)
    assert len(session.failure_history) == 0
    return session


def make_announce_retreat_step_combat_state(
    initial_state: GameState | None = None,
    dice_roller: DiceRoller | None = None,
) -> GameSession:
    session = make_start_of_space_combat_state(initial_state, dice_roller)
    player_a = session.current_state.get_player("A")
    player_b = session.current_state.get_player("B")
    for player in session.current_state.players:
        session.apply_command(
            command=Command(actor=player.name, command_type=CommandType.PASS_START_OF_COMBAT_ROUND),
        )
    for player in (player_a, player_b):
        session.apply_command(
            Command(actor=player.name, command_type=CommandType.USE_ANTI_FIGHTER_BARRAGE),
        )
    assert len(session.failure_history) == 0
    return session


def make_roll_dice_step_state(
    units: frozenset[Unit],
    systems: Galaxy | None = None,
    dice_roller: DiceRoller | None = None,
    players: tuple[Player, ...] | None = None,
) -> GameSession:
    if players is None:
        players = (
            make_player(
                "A",
                command_sheet=CommandSheet.make_from_int(
                    player_name="A",
                    tactic=2,
                    fleet=3,
                    strategy=2,
                    reinforcements=8,
                ),
            ),
            make_player("B"),
        )
    session = make_announce_retreat_step_combat_state(
        initial_state=make_tactical_action_movement_state(
            active_system_id=0,
            units=units,
            players=players,
            systems=systems
            or Galaxy(
                {
                    System(
                        id=0,
                        command_tokens=(CommandToken(player_name="A"),),
                        coordinates=HexCoord(0, 0),
                        planets=frozenset({Planet(0)}),
                    ),
                },
            ),
        ),
        dice_roller=dice_roller,
    )
    assert (
        session.current_state.turn_context.get_space_combat_context().step
        == SpaceCombatStep.ANNOUNCE_RETREATS
    )
    defender = session.current_state.turn_context.get_space_combat_context().defender
    attacker = session.current_state.turn_context.get_space_combat_context().attacker
    for player in defender, attacker:
        session.apply_command(
            command=Command(actor=player, command_type=CommandType.PASS_ANNOUNCE_RETREAT),
        )
    return session


class FixedDiceRoller(DiceRoller):
    def __init__(self, value: int) -> None:
        self.value = value

    def roll(self, num_dice: int) -> list[int]:
        return [self.value] * num_dice
