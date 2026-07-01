import itertools
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    EngineContext,
    ValidationResult,
    make_command_candidates_for_all_players,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import (
    Ability,
    GameState,
    Move,
    SpaceCombatStep,
    TacticalActionStep,
    Window,
)
from src.engine.core.system import System, calculate_move_distance
from src.engine.core.windows import CloseWindowEvent, OpenWindowEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.player import Player
    from src.engine.units.units import Ship, Unit


@dataclass(frozen=True)
class MoveShipCommand(Command):
    ship_id: int
    to_system_id: int


class ConflictingMoveError(ValueError):
    def __init__(self, unit_id: int) -> None:
        super().__init__(f"Conflicting move commands for unit {unit_id}")


def resolve_pending_moves(previous_state: GameState) -> GameState:
    moved_units_by_id: dict[int, Unit] = {}
    for move in previous_state.turn_context.pending_moves:
        unit = previous_state.get_unit_from_id(move.unit_id)
        if unit.unit_id in moved_units_by_id:
            raise ConflictingMoveError(unit.unit_id)
        new_unit = unit.set_system_id(move.to_system_id)
        if new_unit.is_ground_force:
            new_unit = new_unit.cast_to_ground_force().set_planet_id(None)
        moved_units_by_id[new_unit.unit_id] = new_unit
    new_units = frozenset(
        {unit for unit in previous_state.units if unit.unit_id not in moved_units_by_id}
        | set(moved_units_by_id.values()),
    )

    return replace(
        previous_state,
        units=new_units,
        turn_context=replace(previous_state.turn_context, pending_moves=frozenset()),
    )


class ResolvePendingMovesEvent(Event):
    def __repr__(self) -> str:
        return "ResolvePendingMovesEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return resolve_pending_moves(previous_state=previous_state)


class ResolveSpaceCannonOffenseEvent(Event):
    def __init__(self, player: Player, active_system: System) -> None:
        self.player = player
        self.active_system = active_system

    def __repr__(self) -> str:
        return f"ResolveSpaceCannonOffenseEvent:{self.player}:{self.active_system}"

    def apply(self, previous_state: GameState) -> GameState:
        # TODO actually implement space cannon here
        return previous_state.use_ability_for_player(
            player=self.player,
            ability=Ability.SPACE_CANNON,
        )


class ResolveSpaceCannonOffenseCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "ResolveSpaceCannonOffense"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_SPACE_CANNON}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.AFTER_MOVE_SHIPS_STEP):
            return ValidationResult(
                is_valid=False,
                info="Can only resolve space cannon offense immediately after moving ships during "
                "a tactical action",
            )
        if state.active_system is None:
            return ValidationResult(is_valid=False, info="Active system not found")
        if not state.player_may_resolve_space_cannon_in_system(
            command.actor,
            system_id=state.active_system.id,
        ):
            return ValidationResult(
                is_valid=False,
                info=f"{command.actor.name} has no units with SPACE CANNON",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del engine_context
        return [
            ResolveSpaceCannonOffenseEvent(
                player=command.actor,
                active_system=state.get_active_system(),
            ),
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=ResolveSpaceCannonOffenseCommandRule,
        )


class PassSpaceCannonOffenseCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassSpaceCannonOffense"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_SPACE_CANNON}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.AFTER_MOVE_SHIPS_STEP):
            return ValidationResult(
                is_valid=False,
                info="Can only pass on space cannon offense immediately after moving ships during "
                "a tactical action",
            )
        if state.active_system is None:
            return ValidationResult(is_valid=False, info="Active system not found")
        if state.window_context.player_has_passed_on_window(
            command.actor,
            Window.AFTER_MOVE_SHIPS_STEP,
        ):
            return ValidationResult(
                is_valid=False,
                info=f"{command.actor.name} has already passed on space cannon.",
            )
        if state.player_has_resolved_ability_in_current_window(command.actor, Ability.SPACE_CANNON):
            return ValidationResult(
                is_valid=False,
                info=f"{command.actor.name} has already used space cannon.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [PassSpaceCannonEvent(player=command.actor)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=PassSpaceCannonOffenseCommandRule,
        )


class PassSpaceCannonEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def __repr__(self) -> str:
        return f"PassSpaceCannonEvent:{self.player}"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.pass_on_window_for_player(
            player=self.player,
            window=Window.AFTER_MOVE_SHIPS_STEP,
        )  # No state change needed to pass on space cannon offense.


class EndMovementCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "EndMovement"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_MOVEMENT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.is_active_player(command.actor):
            return ValidationResult(is_valid=False, info="Only the active player can end movement")
        if state.turn_context.tactical_action_step != TacticalActionStep.MOVEMENT:
            return ValidationResult(
                is_valid=False,
                info="Can only end movement during the movement step of a tactical action",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return [
            ResolvePendingMovesEvent(),
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=EndMovementCommandRule,
        )


class SpaceCannonOffenseAfterMovementEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolvePendingMovesEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if any(
            state.player_may_resolve_space_cannon_in_system(
                player,
                system_id=state.get_active_system().id,
            )
            for player in state.players
        ):
            return [OpenWindowEvent(Window.AFTER_MOVE_SHIPS_STEP)]
        return [EndMovementStepEvent()]


class CloseSpaceCannonOffenseWindowEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolveSpaceCannonOffenseEvent, PassSpaceCannonEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if (state.active_system is None) or all(
            not state.player_may_resolve_space_cannon_in_system(
                player=player,
                system_id=state.active_system.id,
            )
            for player in state.players
        ):
            return [CloseWindowEvent(window=Window.AFTER_MOVE_SHIPS_STEP)]
        return []


class EndMovementStepEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state

    def __repr__(self) -> str:
        return "EndMovementStepEvent"


class SpaceCombatAfterSpaceCannonOffenseEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {CloseWindowEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del state
        # isinstance check required to access event.window attribute
        if isinstance(event, CloseWindowEvent) and event.window == Window.AFTER_MOVE_SHIPS_STEP:
            return [EndMovementStepEvent()]
        return []


class AddMoveToPendingEvent(Event):
    def __init__(
        self,
        unit_id: int,
        to_system_id: int,
        transported_by_id: int | None = None,
    ) -> None:
        self.unit_id = unit_id
        self.to_system_id = to_system_id
        self.transported_by_id = transported_by_id

    def __repr__(self) -> str:
        return f"AddMoveToPendingEvent:{self.unit_id}:{self.to_system_id}:{self.transported_by_id}"

    def apply(self, previous_state: GameState) -> GameState:
        from_system_id = previous_state.get_unit_from_id(self.unit_id).system_id
        if from_system_id is None:
            raise ConflictingMoveError(self.unit_id)
        move_set = previous_state.turn_context.pending_moves | {
            Move(
                unit_id=self.unit_id,
                from_system_id=from_system_id,
                to_system_id=self.to_system_id,
                transported_by_id=self.transported_by_id,
            ),
        }
        return replace(
            previous_state,
            turn_context=replace(previous_state.turn_context, pending_moves=move_set),
        )


class SelectUnitEvent(Event):
    def __init__(self, ship_id: int | None) -> None:
        self.ship_id = ship_id

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.select_unit(unit_id=self.ship_id)

    def __repr__(self) -> str:
        return f"SelectUnitEvent:{self.ship_id}"


class CapacityShipMoveEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        if (
            isinstance(event, AddMoveToPendingEvent)
            and state.get_unit_from_id(event.unit_id).stats.capacity is not None
        ):
            return [
                SelectUnitEvent(event.unit_id),
                OpenWindowEvent(Window.TRANSPORT_UNITS),
            ]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {AddMoveToPendingEvent}


@dataclass(frozen=True)
class TransportUnitCommand(Command):
    unit_id: int


def get_move_for_unit_id(moves: frozenset[Move], unit_id: int) -> Move:
    return {move for move in moves if move.unit_id == unit_id}.pop()


def get_consumed_capacity_for_unit_id(moves: frozenset[Move], unit_id: int) -> int:
    return len({move for move in moves if move.transported_by_id == unit_id})


def _check_transport_ownership(
    command: TransportUnitCommand,
    unit: Unit,
    carrying_ship: Unit,
) -> ValidationResult:
    if carrying_ship.owner_name != command.actor.name:
        return ValidationResult(is_valid=False, info="Carrying ship belongs to another player.")
    if unit.owner_name != command.actor.name:
        return ValidationResult(is_valid=False, info="Cannot transport another player's units.")
    return ValidationResult(is_valid=True)


def _check_transport_legal(state: GameState, command: TransportUnitCommand) -> ValidationResult:
    unit = state.get_unit_from_id(command.unit_id)
    carrying_ship = state.selected_unit
    if not unit.is_transportable:
        return ValidationResult(is_valid=False, info="Unit is not transportable.")
    ownership_result = _check_transport_ownership(
        command=command,
        unit=unit,
        carrying_ship=carrying_ship,
    )
    if not ownership_result.is_valid:
        return ownership_result
    if (
        carrying_ship.stats.capacity is None
        or carrying_ship.stats.capacity
        <= get_consumed_capacity_for_unit_id(
            moves=state.turn_context.pending_moves,
            unit_id=carrying_ship.unit_id,
        )
    ):
        return ValidationResult(is_valid=False, info="Carrying ship is already full.")
    if unit.system_id != carrying_ship.system_id:
        # NOTE: This is a simplification — once multi-step movement / path-finding is
        # implemented, transports should be allowed to pick up units from any system
        # along the carrier's path, not only its starting system.
        return ValidationResult(
            is_valid=False,
            info="Cannot transport units that are not in the same system as the ship",
        )
    if unit.unit_id in {move.unit_id for move in state.turn_context.pending_moves}:
        return ValidationResult(is_valid=False, info="Unit has already been moved.")

    return ValidationResult(is_valid=True)


class TransportUnitCommandRule(CommandRule[TransportUnitCommand]):
    def __repr__(self) -> str:
        return "TransportUnit"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.TRANSPORT_UNIT}

    @staticmethod
    def candidate_commands(state: GameState) -> list[TransportUnitCommand]:
        return [
            TransportUnitCommand(
                actor=player,
                command_type=CommandType.TRANSPORT_UNIT,
                unit_id=unit.unit_id,
            )
            for player, unit in itertools.product(state.players, state.units)
        ]

    def validate_legality(
        self,
        state: GameState,
        command: TransportUnitCommand,
    ) -> ValidationResult:
        if not state.window_context.is_window_active(Window.TRANSPORT_UNITS):
            return ValidationResult(is_valid=False, info="Cannot transport at this time.")

        return _check_transport_legal(state=state, command=command)

    def derive_events(
        self,
        state: GameState,
        command: TransportUnitCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del engine_context
        carrier_move = get_move_for_unit_id(
            state.turn_context.pending_moves,
            unit_id=state.get_selected_unit_id(),
        )

        return [
            AddMoveToPendingEvent(
                unit_id=command.unit_id,
                to_system_id=carrier_move.to_system_id,
                transported_by_id=carrier_move.unit_id,
            ),
        ]


class PassTransportUnitCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassTransportUnit"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_TRANSPORT_UNIT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.TRANSPORT_UNITS):
            return ValidationResult(is_valid=False, info="You are not in a capacity window.")
        if state.selected_unit.owner_name != command.actor.name:
            return ValidationResult(is_valid=False, info="This transport is not yours.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return [
            CloseWindowEvent(Window.TRANSPORT_UNITS),
            SelectUnitEvent(None),
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=PassTransportUnitCommandRule,
        )


@dataclass(frozen=True)
class MoveProperties:
    ship: Ship
    owner: Player
    active_system: System
    current_system: System


def _check_valid_objects(
    state: GameState,
    command: MoveShipCommand,
) -> tuple[ValidationResult, MoveProperties | None]:
    try:
        ship = state.get_ship_from_id(ship_id=command.ship_id)
    except ValueError:
        return ValidationResult(is_valid=False, info="Invalid ship ID"), None
    try:
        owner = state.get_player(name=ship.owner_name)
    except ValueError:
        return ValidationResult(is_valid=False, info="Invalid ship owner"), None
    active_system = state.active_system
    if active_system is None:
        return ValidationResult(is_valid=False, info="No active system"), None
    current_system = state.get_current_system(ship)
    if current_system is None:
        return ValidationResult(is_valid=False, info="Ship is not in any system"), None
    return ValidationResult(is_valid=True), MoveProperties(
        ship=ship,
        owner=owner,
        active_system=active_system,
        current_system=current_system,
    )


def _check_basic_ownership(
    command: MoveShipCommand,
    state: GameState,
    move_properties: MoveProperties,
) -> ValidationResult:
    if not state.is_active_player(command.actor):
        return ValidationResult(is_valid=False, info="Only the active player can move ships")
    if state.turn_context.tactical_action_step != TacticalActionStep.MOVEMENT:
        return ValidationResult(
            is_valid=False,
            info="Can only move ships during the movement step of a tactical action",
        )
    if command.actor != move_properties.owner:
        return ValidationResult(is_valid=False, info="Player can only move their own ships")
    return ValidationResult(is_valid=True)


def _check_basic_spatial_properties(
    command: MoveShipCommand,
    state: GameState,
    move_properties: MoveProperties,
) -> ValidationResult:
    if command.to_system_id != move_properties.active_system.id:
        return ValidationResult(is_valid=False, info="Can only move ships to the active system")
    if move_properties.current_system.has_command_token(state.active_player):
        return ValidationResult(
            is_valid=False,
            info="Cannot move ships from a system with your command token",
        )
    if move_properties.ship.stats.move is None or (
        calculate_move_distance(
            system_a=move_properties.current_system,
            system_b=move_properties.active_system,
        )
        > move_properties.ship.stats.move
    ):
        return ValidationResult(is_valid=False, info="Ship does not have sufficient move to move")
    return ValidationResult(is_valid=True)


def _validate_tactical_action_move(state: GameState, command: MoveShipCommand) -> ValidationResult:
    object_validation_result, move_properties = _check_valid_objects(state, command)
    if not object_validation_result.is_valid:
        return object_validation_result
    assert move_properties is not None

    basic_ownership_result = _check_basic_ownership(
        command=command,
        state=state,
        move_properties=move_properties,
    )
    if not basic_ownership_result.is_valid:
        return basic_ownership_result

    basic_spatial_result = _check_basic_spatial_properties(
        command=command,
        state=state,
        move_properties=move_properties,
    )
    if not basic_spatial_result.is_valid:
        return basic_spatial_result

    return ValidationResult(is_valid=True)


class MoveShipCommandRule(CommandRule[MoveShipCommand]):
    def __repr__(self) -> str:
        return "MoveShip"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.MOVE_SHIP}

    @staticmethod
    def candidate_commands(state: GameState) -> list[MoveShipCommand]:
        if state.turn_context.tactical_action_step == TacticalActionStep.MOVEMENT:
            return [
                MoveShipCommand(
                    actor=player,
                    command_type=CommandType.MOVE_SHIP,
                    ship_id=unit.unit_id,
                    to_system_id=state.get_active_system().id,
                )
                for player, unit in itertools.product(state.players, state.units)
                if unit.is_ship and unit.owner_name == player.name
            ]
        if (
            state.turn_context.tactical_action_step == TacticalActionStep.SPACE_COMBAT
            and state.turn_context.get_space_combat_context().step == SpaceCombatStep.RETREAT
        ):
            return [
                MoveShipCommand(
                    actor=player,
                    command_type=CommandType.MOVE_SHIP,
                    ship_id=unit.unit_id,
                    to_system_id=system.id,
                )
                for player, unit, system in itertools.product(
                    state.players,
                    state.units,
                    (
                        system
                        for system in state.galaxy
                        if system.is_adjacent_to(state.get_active_system())
                    ),
                )
                if unit.is_ship and unit.owner_name == player.name
            ]
        return []

    def validate_legality(self, state: GameState, command: MoveShipCommand) -> ValidationResult:
        return _validate_tactical_action_move(state, command)

    def derive_events(
        self,
        state: GameState,
        command: MoveShipCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [
            AddMoveToPendingEvent(
                unit_id=command.ship_id,
                to_system_id=command.to_system_id,
            ),
        ]


def get_command_rules() -> list[
    CommandRule[MoveShipCommand] | CommandRule[Command] | CommandRule[TransportUnitCommand]
]:
    return [
        EndMovementCommandRule(),
        MoveShipCommandRule(),
        ResolveSpaceCannonOffenseCommandRule(),
        PassSpaceCannonOffenseCommandRule(),
        TransportUnitCommandRule(),
        PassTransportUnitCommandRule(),
    ]


def get_event_rules() -> list[EventRule]:
    return [
        SpaceCannonOffenseAfterMovementEventRule(),
        SpaceCombatAfterSpaceCannonOffenseEventRule(),
        CloseSpaceCannonOffenseWindowEventRule(),
        CapacityShipMoveEventRule(),
    ]
