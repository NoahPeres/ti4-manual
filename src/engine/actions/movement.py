from collections.abc import Sequence
from dataclasses import dataclass, replace

from src.engine.actions.tactical_action import AdvanceToSpaceCombatStepEvent
from src.engine.core.command import (
    Command,
    CommandRule,
    CommandType,
    ValidationResult,
)
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import (
    Ability,
    GameState,
    HexCoord,
    Move,
    System,
    TacticalActionStep,
    Window,
)
from src.engine.core.player import Player
from src.engine.core.windows import CloseWindowEvent, OpenWindowEvent
from src.engine.units.units import Ship, Unit


@dataclass(frozen=True)
class MoveShipCommand(Command):
    ship_id: int
    to_system_id: int
    transported_unit_ids: frozenset[int] = frozenset()


class ResolvePendingMovesEvent(Event):
    payload = "ResolvePendingMoves"

    def apply(self, previous_state: GameState) -> GameState:
        moved_units: set[Unit] = set()
        for move in previous_state.turn_context.pending_moves:
            ship = previous_state.get_ship_from_id(move.ship_id)
            new_ship = ship.set_system_id(move.to_system_id)
            moved_units.add(new_ship)
            for transported_unit_id in move.transported_unit_ids:
                unit = previous_state.get_unit_from_id(transported_unit_id)
                new_unit = unit.set_system_id(move.to_system_id)
                moved_units.add(new_unit)
        moved_unit_ids = {unit.unit_id for unit in moved_units}
        new_units = frozenset(
            {unit for unit in previous_state.units if unit.unit_id not in moved_unit_ids}
            | moved_units
        )

        return replace(
            previous_state,
            units=new_units,
            turn_context=replace(previous_state.turn_context, pending_moves=frozenset()),
        )


class ResolveSpaceCannonOffenseEvent(Event):
    def __init__(self, player: Player, active_system: System) -> None:
        self.player = player
        self.active_system = active_system
        self.payload = f"ResolveSpaceCannonOffense{player.name}"

    def apply(self, previous_state: GameState) -> GameState:
        # TODO actually implement space cannon here
        return replace(
            previous_state,
            turn_context=previous_state.turn_context.use_ability_for_player(
                player=self.player, ability=Ability.SPACE_CANNON
            ),
        )


class ResolveSpaceCannonOffenseCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "ResolveSpaceCannonOffense"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_SPACE_CANNON}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.is_window_active(Window.AFTER_MOVE_SHIPS_STEP):
            return ValidationResult(
                is_valid=False,
                info="Can only resolve space cannon offense immediately after moving ships during "
                "a tactical action",
            )
        if state.active_system is None:
            return ValidationResult(is_valid=False, info="Active system not found")
        if not state.player_may_resolve_space_cannon_in_system(
            command.actor, system_id=state.active_system.id
        ):
            return ValidationResult(
                is_valid=False, info=f"{command.actor.name} has no eligible units with SPACE CANNON"
            )
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        if state.active_system is None:
            raise ValueError("Invalid active system")
        return [
            ResolveSpaceCannonOffenseEvent(player=command.actor, active_system=state.active_system)
        ]


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

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state, command
        return [
            ResolvePendingMovesEvent(),
        ]


class SpaceCannonOffenseAfterMovementEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        if state.active_system is None:
            raise ValueError("Active system not found")
        if isinstance(event, ResolvePendingMovesEvent) and any(
            state.player_may_resolve_space_cannon_in_system(
                player, system_id=state.active_system.id
            )
            for player in state.players
        ):
            return [OpenWindowEvent(Window.AFTER_MOVE_SHIPS_STEP)]
        return [AdvanceToSpaceCombatStepEvent()]


class CloseSpaceCannonOffenseWindowEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        if not isinstance(event, ResolveSpaceCannonOffenseEvent):
            return []
        if (state.active_system is None) or all(
            not state.player_may_resolve_space_cannon_in_system(
                player=player, system_id=state.active_system.id
            )
            or state.turn_context.player_has_resolved_ability(
                player=player, ability=Ability.SPACE_CANNON
            )
            for player in state.players
        ):
            return [CloseWindowEvent(window=Window.AFTER_MOVE_SHIPS_STEP)]
        return []


class SpaceCombatAfterSpaceCannonOffenseEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del state
        if isinstance(event, CloseWindowEvent) and event.window == Window.AFTER_MOVE_SHIPS_STEP:
            return [AdvanceToSpaceCombatStepEvent()]
        return []


class AddMoveToPendingEvent(Event):
    def __init__(
        self, ship_id: int, to_system_id: int, transported_unit_ids: frozenset[int] = frozenset()
    ) -> None:
        self.ship_id = ship_id
        self.to_system_id = to_system_id
        self.transported_unit_ids = transported_unit_ids

    payload = "AddMoveToPending"

    def apply(self, previous_state: GameState) -> GameState:
        active_system = previous_state.active_system
        if active_system is None:
            raise ValueError("No active system in state when applying AddMoveToPendingEvent")
        move_set = previous_state.turn_context.pending_moves | {
            Move(
                ship_id=self.ship_id,
                from_system_id=active_system.id,
                to_system_id=self.to_system_id,
                transported_unit_ids=self.transported_unit_ids,
            )
        }
        return replace(
            previous_state,
            turn_context=replace(previous_state.turn_context, pending_moves=move_set),
        )


def distance(coordinates_a: HexCoord, coordinates_b: HexCoord) -> int:
    """Convention here: Mecatol Rex is (0,0), up is y+=1, up-right is x+=1 and y+=1,
    down-right is x+=1 and y-=1. That is, there are two cases:
    If the point is between y and x axes, then you can always reach it along a sequence
    of up-right moves, plus some number of down-right moves. The number of up-right moves is
    min(|dx|, |dy|), and the number of remaining moves is abs(|dx| - |dy|).
    If the point is between y and -x axes, then you can always reach it along a sequence
    of up moves plus some number of up-left moves. The number of up moves is |dy|, and the
    number of up-left moves is |dx|. Negative values of dx and dy correspond to down and
    down-right moves, respectively."""
    dx = coordinates_b.x - coordinates_a.x
    dy = coordinates_b.y - coordinates_a.y
    if dx * dy >= 0:
        return max(abs(dx), abs(dy))
    return abs(dx) + abs(dy)


def calculate_move_distance(system_a: System, system_b: System) -> int:
    if system_a.coordinates is None or system_b.coordinates is None:
        raise ValueError("Cannot calculate move distance between systems without coordinates")
    return distance(system_a.coordinates, system_b.coordinates)


@dataclass(frozen=True)
class MoveProperties:
    ship: Ship
    owner: Player
    active_system: System
    current_system: System
    transported_units: frozenset[Unit] = frozenset()


def _check_valid_objects(
    state: GameState, command: MoveShipCommand
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
    try:
        transported_units = frozenset(
            state.get_unit_from_id(unit_id=unit_id) for unit_id in command.transported_unit_ids
        )
    except ValueError:
        return ValidationResult(is_valid=False, info="Invalid transported unit ID"), None
    return ValidationResult(is_valid=True), MoveProperties(
        ship=ship,
        owner=owner,
        active_system=active_system,
        current_system=current_system,
        transported_units=transported_units,
    )


def _validate_tactical_action_move(state: GameState, command: MoveShipCommand) -> ValidationResult:
    object_validation_result, move_properties = _check_valid_objects(state, command)
    if not object_validation_result.is_valid:
        return object_validation_result
    assert move_properties is not None
    if not state.is_active_player(command.actor):
        return ValidationResult(is_valid=False, info="Only the active player can move ships")
    if state.turn_context.tactical_action_step != TacticalActionStep.MOVEMENT:
        return ValidationResult(
            is_valid=False,
            info="Can only move ships during the movement step of a tactical action",
        )
    if command.actor != move_properties.owner:
        return ValidationResult(is_valid=False, info="Player can only move their own ships")
    if command.to_system_id != move_properties.active_system.id:
        return ValidationResult(is_valid=False, info="Can only move ships to the active system")
    if move_properties.current_system.has_command_token(state.active_player):
        return ValidationResult(
            is_valid=False, info="Cannot move ships from a system with your command token"
        )
    if move_properties.ship.stats.move is None or (
        calculate_move_distance(
            system_a=move_properties.current_system,
            system_b=move_properties.active_system,
        )
        > move_properties.ship.stats.move
    ):
        return ValidationResult(is_valid=False, info="Ship does not have sufficient move to move")
    capacity_validation_result = _validate_capacity_for_transport(
        move_properties.ship, move_properties.transported_units
    )
    if not capacity_validation_result.is_valid:
        return capacity_validation_result

    return ValidationResult(is_valid=True)


def _validate_capacity_for_transport(
    ship: Ship, transported_units: frozenset[Unit]
) -> ValidationResult:
    if len(transported_units) == 0:
        return ValidationResult(is_valid=True)
    if ship.stats.capacity is None:
        return ValidationResult(
            is_valid=False, info="Cannot transport units with a ship that has no capacity"
        )
    if len(transported_units) > ship.stats.capacity:
        return ValidationResult(
            is_valid=False,
            info=f"Cannot transport {len(transported_units)} units with"
            f" capacity {ship.stats.capacity}",
        )
    not_transportable_units = frozenset(
        unit for unit in transported_units if not unit.is_transportable
    )
    if not_transportable_units:
        return ValidationResult(
            is_valid=False,
            info="Cannot transport non-transportable units: "
            f"{[unit.kind for unit in not_transportable_units]}",
        )
    if any(unit.owner_name != ship.owner_name for unit in transported_units):
        return ValidationResult(
            is_valid=False,
            info="Cannot transport units that do not belong to the same player as the ship",
        )
    if any(unit.system_id != ship.system_id for unit in transported_units):
        # NOTE: This is a simplification — once multi-step movement / path-finding is
        # implemented, transports should be allowed to pick up units from any system
        # along the carrier's path, not only its starting system.
        return ValidationResult(
            is_valid=False,
            info="Cannot transport units that are not in the same system as the ship",
        )
    return ValidationResult(is_valid=True)


class MoveShipCommandRule(CommandRule[MoveShipCommand]):
    def __repr__(self) -> str:
        return "MoveShip"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.MOVE_SHIP}

    def validate_legality(self, state: GameState, command: MoveShipCommand) -> ValidationResult:
        return _validate_tactical_action_move(state, command)

    def derive_events(self, state: GameState, command: MoveShipCommand) -> Sequence[Event]:
        del state
        return [
            AddMoveToPendingEvent(
                ship_id=command.ship_id,
                to_system_id=command.to_system_id,
                transported_unit_ids=command.transported_unit_ids,
            )
        ]


def get_command_rules() -> list[CommandRule[MoveShipCommand]]:
    return [EndMovementCommandRule(), MoveShipCommandRule(), ResolveSpaceCannonOffenseCommandRule()]


def get_event_rules() -> list[EventRule]:
    return [
        SpaceCannonOffenseAfterMovementEventRule(),
        SpaceCombatAfterSpaceCannonOffenseEventRule(),
        CloseSpaceCannonOffenseWindowEventRule(),
    ]
