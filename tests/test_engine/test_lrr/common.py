from src.engine.actions.movement import MoveShipCommand
from src.engine.actions.tactical_action import ActivateCommand
from src.engine.core.command import Command
from src.engine.core.game_engine import CommandType, GameEngine
from src.engine.core.game_session import GameSession
from src.engine.core.game_state import (
    Galaxy,
    GameState,
    HexCoord,
    Phase,
    System,
    TacticalActionStep,
    TurnContext,
)
from src.engine.core.invariants import make_all_invariants
from src.engine.core.player import CommandSheet, Player
from src.engine.core.ti4_rules_engine import TI4RulesEngine
from src.engine.strategy_cards import StrategyCard
from src.engine.tokens import CommandToken
from src.engine.units.units import ShipKind, Unit, make_unit_with_id


class InvalidPlayerCountError(ValueError):
    pass


def get_default_game_engine() -> GameEngine:
    return GameEngine(rules_engine=TI4RulesEngine(), invariants=make_all_invariants())


def make_basic_session_from_players(
    players: tuple[Player, ...],
    initial_state: GameState | None = None,
) -> GameSession:
    engine = get_default_game_engine()
    if len(players) == 0:
        raise InvalidPlayerCountError
    return GameSession(
        initial_state=initial_state
        or GameState(
            players=players,
            active_player=players[0],
            phase=Phase.ACTION,
            galaxy=frozenset({System(id=0, command_tokens=()), System(id=1, command_tokens=())}),
        ),
        engine=engine,
    )


def make_player(
    name: str,
    strategy_cards: tuple[StrategyCard, ...] = (),
) -> Player:
    return Player(
        name=name,
        strategy_cards=strategy_cards,
        command_sheet=CommandSheet.make_from_int(name, tactic=3, fleet=3, strategy=2),
        has_passed=False,
    )


def make_tactical_action_movement_state(
    active_system_id: int,
    units: frozenset[Unit] | None = None,
    player_names: list[str] | None = None,
    systems: frozenset[System] | None = None,
) -> GameState:
    if player_names is None:
        player_names = ["A"]
    players = [
        make_player(name=name, strategy_cards=(StrategyCard(name="A", initiative=i),))
        for i, name in enumerate(player_names)
    ]
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
        systems = frozenset(
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
        active_player=players[0],
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
    galaxy = galaxy or frozenset({System(id=0, command_tokens=()), System(id=1, command_tokens=())})
    turn_context = turn_context or TurnContext(
        has_initiated_action=True,
        tactical_action_step=TacticalActionStep.MOVEMENT,
        active_system_id=0,
    )
    return GameState(
        players=players,
        active_player=active_player,
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


def activate_command(actor: Player, system_id: int) -> ActivateCommand:
    return ActivateCommand(
        actor=actor,
        command_type=CommandType.INITIATE_TACTICAL_ACTION,
        system_id=system_id,
    )


def move_command(
    actor: Player,
    ship_id: int,
    to_system_id: int,
    transported_unit_ids: frozenset[int] = frozenset(),
) -> MoveShipCommand:
    return MoveShipCommand(
        actor=actor,
        command_type=CommandType.MOVE_SHIP,
        ship_id=ship_id,
        to_system_id=to_system_id,
        transported_unit_ids=transported_unit_ids,
    )


def action_command(actor: Player, command_type: CommandType) -> Command:
    return Command(actor=actor, command_type=command_type)


def end_movement(session: GameSession, state: GameState) -> GameState:
    return session.apply_command(
        command=action_command(state.active_player, CommandType.END_MOVEMENT),
    )


def resolve_space_cannon(session: GameSession, state: GameState) -> GameState:
    for player in state.players:
        assert state.active_system is not None
        if state.player_may_resolve_space_cannon_in_system(
            player=player,
            system_id=state.active_system.id,
        ):
            state = session.apply_command(
                command=action_command(player, CommandType.USE_SPACE_CANNON),
            )
    return state


def pass_space_cannon_window(session: GameSession, state: GameState) -> GameState:
    assert state.active_system is not None
    for player in state.players:
        state = session.apply_command(
            command=action_command(player, CommandType.PASS_SPACE_CANNON),
        )
    return state


def begin_invasion(session: GameSession, state: GameState) -> GameState:
    return pass_space_cannon_window(session, end_movement(session, state))


def pass_bombardment_window(session: GameSession, state: GameState) -> GameState:
    assert state.active_system is not None
    return session.apply_command(
        command=action_command(state.active_player, CommandType.PASS_BOMBARDMENT),
    )
