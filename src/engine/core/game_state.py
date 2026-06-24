from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Self

from src.engine.core.system import System
from src.engine.tokens import CommandToken

if TYPE_CHECKING:
    from src.engine.core.player import CommandTokenPool, Player
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


class SpaceCombatParticipant(StrEnum):
    ATTACKER = "attacker"
    DEFENDER = "defender"


class PlayerNotParticipantInCombatError(ValueError):
    pass


@dataclass(frozen=True)
class RetreatDeclaration:
    attacker_has_declared: bool | None = None
    defender_has_declared: bool | None = None

    def announce_attacker_retreat(self, *, is_retreating: bool) -> Self:
        return replace(self, attacker_has_declared=is_retreating)

    def announce_defender_retreat(self, *, is_retreating: bool) -> Self:
        return replace(self, defender_has_declared=is_retreating)

    def get_declaration_by_participant(self, participant: SpaceCombatParticipant) -> bool | None:
        return {
            SpaceCombatParticipant.ATTACKER: self.attacker_has_declared,
            SpaceCombatParticipant.DEFENDER: self.defender_has_declared,
        }[participant]

    @property
    def both_players_have_responded(self) -> bool:
        return self.attacker_has_declared is not None and self.defender_has_declared is not None

    def get_retreating_player_name(self, combat_context: SpaceCombatContext) -> str | None:
        if self.defender_has_declared:
            return combat_context.defender.name
        if self.attacker_has_declared:
            return combat_context.attacker.name
        return None


class InvalidRetreatError(ValueError):
    pass


@dataclass(frozen=True)
class CombatRoll:
    unit_id: int
    value: int
    hit: bool


@dataclass(frozen=True)
class SpaceCombatContext:
    step: SpaceCombatStep
    round_number: int
    attacker: Player
    defender: Player
    assigned_hits: frozenset[int] = field(default_factory=frozenset[int])
    retreat_declaration: RetreatDeclaration = field(default_factory=RetreatDeclaration)
    attacker_combat_rolls: tuple[CombatRoll, ...] = field(default_factory=tuple[CombatRoll, ...])
    defender_combat_rolls: tuple[CombatRoll, ...] = field(default_factory=tuple[CombatRoll, ...])
    attacker_hits_assigned: int = 0
    defender_hits_assigned: int = 0
    current_hits_assignee: Player | None = None

    def assign_hit(self, unit_id: int, player: Player) -> Self:
        participant = self.get_participant_by_player(player)
        new = self
        if participant == SpaceCombatParticipant.ATTACKER:
            new = replace(self, attacker_hits_assigned=self.attacker_hits_assigned + 1)
        elif participant == SpaceCombatParticipant.DEFENDER:
            new = replace(self, defender_hits_assigned=self.defender_hits_assigned + 1)
        return replace(new, assigned_hits=frozenset(self.assigned_hits | {unit_id}))

    def announce_retreat(self, *, player: Player, is_retreating: bool) -> Self:
        if player == self.attacker:
            return replace(
                self,
                retreat_declaration=self.retreat_declaration.announce_attacker_retreat(
                    is_retreating=is_retreating,
                ),
            )
        if player == self.defender:
            return replace(
                self,
                retreat_declaration=self.retreat_declaration.announce_defender_retreat(
                    is_retreating=is_retreating,
                ),
            )
        raise InvalidRetreatError

    @property
    def declared_retreat_name(self) -> str | None:
        return self.retreat_declaration.get_retreating_player_name(self)

    def get_participant_by_player(self, player: Player) -> SpaceCombatParticipant:
        if self.attacker == player:
            return SpaceCombatParticipant.ATTACKER
        if self.defender == player:
            return SpaceCombatParticipant.DEFENDER
        raise PlayerNotParticipantInCombatError

    def total_hits_for_player(self, player: Player) -> int:
        return sum(1 for combat_roll in self.get_combat_rolls_for_player(player) if combat_roll.hit)

    def get_combat_rolls_for_player(self, player: Player) -> tuple[CombatRoll, ...]:
        participant = self.get_participant_by_player(player)
        match participant:
            case SpaceCombatParticipant.ATTACKER:
                return self.attacker_combat_rolls
            case SpaceCombatParticipant.DEFENDER:
                return self.defender_combat_rolls

    def register_combat_roll(
        self,
        combat_roll: CombatRoll,
        participant: SpaceCombatParticipant,
    ) -> Self:
        match participant:
            case SpaceCombatParticipant.ATTACKER:
                return replace(
                    self,
                    attacker_combat_rolls=(*self.attacker_combat_rolls, combat_roll),
                )
            case SpaceCombatParticipant.DEFENDER:
                return replace(
                    self,
                    defender_combat_rolls=(*self.defender_combat_rolls, combat_roll),
                )

    def unassigned_hits_for_player(self, player: Player) -> int:
        participant = self.get_participant_by_player(player)
        match participant:
            case SpaceCombatParticipant.ATTACKER:
                return self.total_hits_for_player(self.defender) - self.attacker_hits_assigned
            case SpaceCombatParticipant.DEFENDER:
                return self.total_hits_for_player(self.attacker) - self.defender_hits_assigned

    def set_hits_assignee(self, player: Player | None) -> Self:
        return replace(self, current_hits_assignee=player)

    def reset_combat_round(self) -> Self:
        return replace(
            self,
            assigned_hits=frozenset({}),
            attacker_combat_rolls=(),
            attacker_hits_assigned=0,
            current_hits_assignee=None,
            defender_combat_rolls=(),
            defender_hits_assigned=0,
            retreat_declaration=RetreatDeclaration(),
            round_number=self.round_number + 1,
            step=SpaceCombatStep.ANNOUNCE_RETREATS,
        )


class Phase(StrEnum):
    STRATEGY = "strategy"
    ACTION = "action"
    STATUS = "status"
    AGENDA = "agenda"


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
    ANTI_FIGHTER_BARRAGE = "anti_fighter_barrage"


class Window(StrEnum):
    AFTER_MOVE_SHIPS_STEP = "after_move_ships_step"
    TACTICAL_ACTION_BOMBARDMENT = "tactical_action_bombardment"
    START_OF_SPACE_COMBAT = "start_of_space_combat"
    START_OF_FIRST_ROUND_OF_SPACE_COMBAT = "start_of_first_round_of_space_combat"
    START_OF_SPACE_COMBAT_ROUND = "start_of_space_combat_round"
    END_OF_SPACE_COMBAT = "end_of_space_combat"
    END_OF_SPACE_COMBAT_ROUND = "end_of_space_combat_round"
    ANTI_FIGHTER_BARRAGE = "anti_fighter_barrage"
    BEFORE_ASSIGNING_HITS = "before_assigning_hits"
    MUST_CHOOSE_POOL_FOR_REMOVE_COMMAND_TOKEN = "must_choose_pool_for_remove_command_token"


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
    retreat_system_id: int | None = None
    pending_moves: frozenset[Move] = field(default_factory=frozenset[Move])
    pending_invasion_commits: frozenset[InvasionCommit] = field(
        default_factory=frozenset[InvasionCommit],
    )

    def get_space_combat_context(self) -> SpaceCombatContext:
        if self.space_combat_context is None:
            raise ContextNotFoundError("space_combat")
        return self.space_combat_context

    def get_retreat_system_id(self) -> int:
        if self.retreat_system_id is None:
            raise InvalidRetreatError
        return self.retreat_system_id

    def set_retreat_system_id(self, retreat_system_id: int | None) -> Self:
        return replace(self, retreat_system_id=retreat_system_id)


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


class Galaxy(frozenset[System]):
    def get_adjacent_systems(self, system_id: int) -> set[System]:
        system = self.get_system(system_id)
        return {other_system for other_system in self if system.is_adjacent_to(other_system)}

    def get_system(self, system_id: int) -> System:
        try:
            return next(system for system in self if system.id == system_id)
        except StopIteration:
            raise ComponentNotFoundError(f"system:{system_id}") from None

    def combine(self, other: Galaxy) -> Galaxy:
        return Galaxy(self | other)


class ComponentNotFoundError(ValueError):
    def __init__(self, component_name: str) -> None:
        super().__init__(f"Component not found: {component_name}")


class ContextNotFoundError(ValueError):
    def __init__(self, context_name: str) -> None:
        super().__init__(f"Context not found: {context_name}")


class InvalidActiveSystemError(ValueError):
    def __init__(self, message: str = "Active system not found") -> None:
        super().__init__(message)


class CannotInferDefenderError(ValueError):
    def __init__(self, number_of_eligible_players: int) -> None:
        super().__init__(f"Number of eligible players={number_of_eligible_players}")


@dataclass(frozen=True)
class GameState:
    players: tuple[Player, ...]
    active_player_name: str
    phase: Phase
    galaxy: Galaxy
    turn_context: TurnContext = field(
        default_factory=lambda: TurnContext(has_initiated_action=False),
    )
    units: frozenset[Unit] = frozenset()
    window_context: WindowContext = field(default_factory=WindowContext)

    @property
    def active_player(self) -> Player:
        return self.get_player(self.active_player_name)

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
        return (
            self.turn_context.has_initiated_action or self.active_player.has_passed
        ) and self.turn_context.space_combat_context is None

    @property
    def active_system(self) -> System | None:
        if self.turn_context.active_system_id is None:
            return None
        return self.galaxy.get_system(system_id=self.turn_context.active_system_id)

    def get_active_system(self) -> System:
        if self.active_system is None:
            raise InvalidActiveSystemError
        return self.active_system

    def get_player(self, name: str) -> Player:
        try:
            return next(player for player in self.players if player.name == name)
        except StopIteration:
            raise ComponentNotFoundError(f"player:{name}") from None

    def get_current_system(self, unit: Unit) -> System | None:
        return self.galaxy.get_system(unit.system_id) if unit.system_id is not None else None

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
        return not self.player_has_resolved_ability_in_current_window(
            player=player,
            ability=Ability.SPACE_CANNON,
        ) and not self.window_context.player_has_passed_on_window(
            player=player,
            window=Window.AFTER_MOVE_SHIPS_STEP,
        )

    def player_may_resolve_bombardment_in_system(self, player: Player, system_id: int) -> bool:
        # TODO: deferred - return to this when we properly implement BOMBARDMENT unit ability
        del system_id
        return not self.player_has_resolved_ability_in_current_window(
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

    def player_has_resolved_ability_in_current_window(
        self,
        player: Player,
        ability: Ability,
    ) -> bool:
        return (
            ability
            in self.window_context.get_or_create_ability_tracker(player=player).abilities_used
        )

    def get_units_in_system(self, system_id: int, player_name: str | None = None) -> set[Unit]:
        return {
            unit
            for unit in self.units
            if unit.system_id == system_id
            and (player_name is None or unit.owner_name == player_name)
        }

    def get_ships_in_system(self, system_id: int, player_name: str | None = None) -> set[Ship]:
        return {
            unit.cast_to_ship()
            for unit in self.units
            if unit.system_id == system_id
            and unit.is_ship
            and (player_name is None or unit.owner_name == player_name)
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

    def get_pending_assigned_hits(self) -> frozenset[int]:
        if self.turn_context.space_combat_context is None:
            return frozenset()
        return self.turn_context.space_combat_context.assigned_hits

    def remove_unit(self, unit_id: int) -> Self:
        return replace(
            self,
            units=frozenset(unit for unit in self.units if unit.unit_id != unit_id)
            | {self.get_unit_from_id(unit_id=unit_id).set_system_id(None)},
        )

    def assign_hit(self, unit_id: int, player: Player) -> Self:
        context = self.turn_context.get_space_combat_context()
        if self.get_current_system(self.get_unit_from_id(unit_id)) is None:
            raise ComponentNotFoundError(str(unit_id))
        return self.set_space_combat_context(
            context.assign_hit(unit_id, player=player),
        ).remove_unit(unit_id)

    def player_may_resolve_afb_in_system(self, player: Player, system_id: int) -> bool:
        # TODO: deferred - return to this when we properly implement SPACE CANNON unit ability
        del system_id
        return not self.player_has_resolved_ability_in_current_window(
            player=player,
            ability=Ability.ANTI_FIGHTER_BARRAGE,
        ) and not self.window_context.player_has_passed_on_window(
            player=player,
            window=Window.ANTI_FIGHTER_BARRAGE,
        )

    def get_defender_in_system(self, system_id: int) -> Player:
        units = self.get_ships_in_system(system_id)
        non_active_players = {
            ship.owner_name for ship in units if ship.owner_name != self.active_player.name
        }
        num_eligible_players = len(non_active_players)
        if num_eligible_players != 1:
            raise CannotInferDefenderError(num_eligible_players)
        return self.get_player(non_active_players.pop())

    def register_combat_roll(self, combat_roll: CombatRoll) -> Self:
        if self.turn_context.space_combat_context is None:
            raise ContextNotFoundError("space_combat")
        participant = self.turn_context.space_combat_context.get_participant_by_player(
            self.get_player(self.get_unit_from_id(unit_id=combat_roll.unit_id).owner_name),
        )

        return self.set_space_combat_context(
            self.turn_context.space_combat_context.register_combat_roll(
                combat_roll,
                participant=participant,
            ),
        )

    def reinforcements_for_player(self, player: Player) -> set[Unit]:
        return {
            unit
            for unit in self.units
            if unit.owner_name == player.name and unit.is_in_reinforcements
        }

    def get_units_in_space_area_of_system(
        self,
        system_id: int,
        player_name: str | None = None,
    ) -> set[Unit]:
        return {
            unit
            for unit in self.get_units_in_system(system_id=system_id, player_name=player_name)
            if unit.is_in_space_area
        }

    def withdraw_command_token(self, player_name: str, from_pool: CommandTokenPool) -> Self:
        current_player = self.get_player(player_name)
        updated_player = replace(
            current_player,
            command_sheet=current_player.command_sheet.remove_token_from_pool(
                command_token=CommandToken(player_name),
                pool=from_pool,
            ),
        )
        return replace(
            self,
            players=tuple(updated_player if p.name == player_name else p for p in self.players),
        )

    def place_command_token_in_system(self, player_name: str, system_id: int) -> Self:
        return replace(
            self,
            galaxy=Galaxy(
                {system for system in self.galaxy if system.id != system_id}
                | {
                    self.galaxy.get_system(system_id).place_command_token(
                        CommandToken(player_name),
                    ),
                },
            ),
        )
