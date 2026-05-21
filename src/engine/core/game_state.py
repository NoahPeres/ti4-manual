from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from src.engine.core.player import Player
    from src.engine.tokens import CommandToken
    from src.engine.units.units import GroundForce, Ship, Unit


class TacticalActionStep(StrEnum):
    ACTIVATION = "activation"
    MOVEMENT = "movement"
    SPACE_COMBAT = "space_combat"
    INVASION = "invasion"
    PRODUCTION = "production"


class SpaceCombatStep(StrEnum):
    ANTI_FIGHTER_BARRAGE = "anti_fighter_barrage"
    ANNOUNCE_RETREATS = "announce_retreats"
    ROLL_DICE = "roll_dice"
    ASSIGN_HITS = "assign_hits"
    RETREAT = "retreat"


@dataclass(frozen=True)
class SpaceCombatContext:
    step: SpaceCombatStep
    round_number: int


class Phase(StrEnum):
    STRATEGY = "strategy"
    ACTION = "action"
    STATUS = "status"
    AGENDA = "agenda"


@dataclass(frozen=True)
class HexCoord:
    x: int
    y: int


@dataclass(frozen=True)
class System:
    id: int
    command_tokens: tuple[CommandToken, ...]
    coordinates: HexCoord | None = None

    def has_command_token(self, player: Player) -> bool:
        return any(token.player_name == player.name for token in self.command_tokens)


@dataclass(frozen=True)
class Move:
    ship_id: int
    from_system_id: int
    to_system_id: int
    transported_unit_ids: frozenset[int] = frozenset()


@dataclass(frozen=True)
class InvasionCommit:
    ground_force_id: int
    to_planet_id: int


class Ability(StrEnum):
    SPACE_CANNON = "space_cannon"
    BOMBARDMENT = "bombardment"


class Window(StrEnum):
    AFTER_MOVE_SHIPS_STEP = "after_move_ships_step"
    TACTICAL_ACTION_BOMBARDMENT = "tactical_action_bombardment"
    START_OF_SPACE_COMBAT = "start_of_space_combat"
    START_OF_FIRST_ROUND_OF_SPACE_COMBAT = "start_of_first_round_of_space_combat"
    START_OF_A_ROUND_OF_SPACE_COMBAT = "start_of_a_round_of_space_combat"


@dataclass(frozen=True)
class PlayerAbilityTracker:
    player_name: str
    abilities_used: frozenset[Ability]
    passed_windows: frozenset[Window] = field(default_factory=frozenset[Window])

    def use_ability(self, ability: Ability) -> PlayerAbilityTracker:
        return replace(self, abilities_used=frozenset(self.abilities_used | {ability}))

    def pass_on_window(self, window: Window) -> PlayerAbilityTracker:
        return replace(self, passed_windows=frozenset(self.passed_windows | {window}))

    def has_passed_on_window(self, window: Window) -> bool:
        return window in self.passed_windows


@dataclass(frozen=True)
class TurnContext:
    has_initiated_action: bool
    tactical_action_step: TacticalActionStep | None = None
    space_combat_context: SpaceCombatContext | None = None
    active_system_id: int | None = None
    pending_moves: frozenset[Move] = field(default_factory=frozenset[Move])
    pending_invasion_commits: frozenset[InvasionCommit] = field(
        default_factory=frozenset[InvasionCommit],
    )


class IllegalWindowOperationError(RuntimeError):
    def __init__(self, operation: str) -> None:
        super().__init__(f"Illegal window operation: {operation}")


@dataclass(frozen=True)
class WindowContext:
    active_windows: tuple[Window, ...] = field(default_factory=tuple)
    player_abilities_in_window: frozenset[PlayerAbilityTracker] = field(
        default_factory=frozenset[PlayerAbilityTracker],
    )

    def get_or_create_ability_tracker(self, player: Player) -> PlayerAbilityTracker:
        for tracker in self.player_abilities_in_window:
            if tracker.player_name == player.name:
                return tracker
        return PlayerAbilityTracker(player_name=player.name, abilities_used=frozenset[Ability]())

    def use_ability_for_player(self, player: Player, ability: Ability) -> Self:
        tracker = self.get_or_create_ability_tracker(player)
        return replace(
            self,
            player_abilities_in_window=frozenset(
                {
                    other_tracker
                    for other_tracker in self.player_abilities_in_window
                    if other_tracker != tracker
                }
                | {tracker.use_ability(ability)},
            ),
        )

    def is_window_active(self, window: Window) -> bool:
        return window in self.active_windows

    def pass_on_window_for_player(self, player: Player, window: Window) -> Self:
        if not self.is_window_active(window):
            raise IllegalWindowOperationError("pass_on_window_for_player")
        tracker = self.get_or_create_ability_tracker(player)
        return replace(
            self,
            player_abilities_in_window=frozenset(
                {
                    other_tracker
                    for other_tracker in self.player_abilities_in_window
                    if other_tracker != tracker
                }
                | {tracker.pass_on_window(window=window)},
            ),
        )

    def player_has_passed_on_window(self, player: Player, window: Window) -> bool:
        tracker = self.get_or_create_ability_tracker(player)
        return tracker.has_passed_on_window(window=window)


Galaxy = frozenset[System]


class ComponentNotFoundError(ValueError):
    def __init__(self, component_name: str) -> None:
        super().__init__(f"Component not found: {component_name}")


@dataclass(frozen=True)
class GameState:
    players: tuple[Player, ...]
    active_player: Player
    phase: Phase
    galaxy: Galaxy
    turn_context: TurnContext = field(
        default_factory=lambda: TurnContext(has_initiated_action=False),
    )
    units: frozenset[Unit] = frozenset()
    window_context: WindowContext = field(default_factory=WindowContext)

    @property
    def initiative_order(self) -> tuple[Player, ...]:
        return tuple(
            sorted(
                self.players,
                key=lambda p: p.initiative,
            ),
        )

    @property
    def initiative_order_unpassed(self) -> tuple[Player, ...]:
        return tuple(player for player in self.initiative_order if not player.has_passed)

    @property
    def has_taken_turn(self) -> bool:
        return self.turn_context.has_initiated_action or self.active_player.has_passed

    @property
    def active_system(self) -> System | None:
        if self.turn_context.active_system_id is None:
            return None
        return self.get_system(system_id=self.turn_context.active_system_id)

    def get_system(self, system_id: int) -> System:
        try:
            return next(system for system in self.galaxy if system.id == system_id)
        except StopIteration:
            raise ComponentNotFoundError(f"system:{system_id}") from None

    def get_player(self, name: str) -> Player:
        try:
            return next(player for player in self.players if player.name == name)
        except StopIteration:
            raise ComponentNotFoundError(f"player:{name}") from None

    def get_current_system(self, unit: Unit) -> System | None:
        return self.get_system(unit.system_id) if unit.system_id is not None else None

    def get_unit_from_id(self, unit_id: int) -> Unit:
        try:
            return next(unit for unit in self.units if unit.unit_id == unit_id)
        except StopIteration:
            raise ComponentNotFoundError(f"unit:{unit_id}") from None

    def get_ship_from_id(self, ship_id: int) -> Ship:
        return self.get_unit_from_id(unit_id=ship_id).cast_to_ship()

    def get_ground_force_from_id(self, ground_force_id: int) -> GroundForce:
        return self.get_unit_from_id(unit_id=ground_force_id).cast_to_ground_force()

    def is_active_player(self, player: Player) -> bool:
        return self.active_player == player

    def use_ability_for_player(self, player: Player, ability: Ability) -> Self:
        return replace(
            self,
            window_context=self.window_context.use_ability_for_player(player, ability),
        )

    def pass_on_window_for_player(self, player: Player, window: Window) -> Self:
        return replace(
            self,
            window_context=self.window_context.pass_on_window_for_player(player, window),
        )

    def player_may_resolve_space_cannon_in_system(self, player: Player, system_id: int) -> bool:
        # TODO: deferred - return to this when we properly implement SPACE CANNON unit ability
        del system_id
        return not self.player_has_resolved_ability_is_current_window(
            player=player,
            ability=Ability.SPACE_CANNON,
        ) and not self.window_context.player_has_passed_on_window(
            player=player,
            window=Window.AFTER_MOVE_SHIPS_STEP,
        )

    def player_may_resolve_bombardment_in_system(self, player: Player, system_id: int) -> bool:
        # TODO: deferred - return to this when we properly implement BOMBARDMENT unit ability
        del system_id
        return not self.player_has_resolved_ability_is_current_window(
            player=player,
            ability=Ability.BOMBARDMENT,
        ) and not self.window_context.player_has_passed_on_window(
            player=player,
            window=Window.TACTICAL_ACTION_BOMBARDMENT,
        )

    def player_may_resolve_production_in_system(self, player: Player, system_id: int) -> bool:
        # TODO: deferred - return to this when we properly implement PRODUCTION unit ability
        del player, system_id
        return True

    def player_has_resolved_ability_is_current_window(
        self,
        player: Player,
        ability: Ability,
    ) -> bool:
        return (
            ability
            in self.window_context.get_or_create_ability_tracker(player=player).abilities_used
        )

    def get_units_in_system(self, system_id: int) -> set[Unit]:
        return {unit for unit in self.units if unit.system_id == system_id}

    def get_ships_in_system(self, system_id: int) -> set[Ship]:
        return {
            unit.cast_to_ship()
            for unit in self.units
            if unit.system_id == system_id and unit.is_ship
        }

    def close_all_windows(self) -> Self:
        return replace(
            self,
            window_context=replace(self.window_context, active_windows=()),
        )

    def set_space_combat_context(self, space_combat_context: SpaceCombatContext) -> Self:
        return replace(
            self,
            turn_context=replace(self.turn_context, space_combat_context=space_combat_context),
        )
