from __future__ import annotations

import itertools
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable, Final

from src.engine.actions.movement import (
    AddMoveToPendingEvent,
    OpenWindowEvent,
    resolve_pending_moves,
)
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
    GameState,
    InvalidRetreatError,
    SpaceCombatContext,
    SpaceCombatParticipant,
    SpaceCombatStep,
    UnitAbility,
    Window,
)
from src.engine.core.player import CommandTokenPool
from src.engine.core.windows import CloseWindowEvent

from .cleanup import RemoveUnitEvent
from .shared import get_active_system_id

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.units.units import Ship


class ResolveAntiFighterBarrageEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player_name = player_name

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.use_ability_for_player(
            player_name=self.player_name,
            ability=UnitAbility.ANTI_FIGHTER_BARRAGE,
        )

    def __repr__(self) -> str:
        return f"ResolveAntiFighterBarrageEvent:{self.player_name}"


class PassAntiFighterBarrageEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player_name = player_name

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.pass_on_window_for_player(
            player_name=self.player_name,
            window=Window.ANTI_FIGHTER_BARRAGE,
        )

    def __repr__(self) -> str:
        return f"PassAntiFighterBarrageEvent:{self.player_name}"


class UseAntiFighterBarrageCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "UseAntiFighterBarrageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.USE_ANTI_FIGHTER_BARRAGE}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.turn_context.space_combat_context is None:
            return ValidationResult(
                is_valid=False,
                info="Anti-fighter barrage only valid during space combat.",
            )
        if (
            state.turn_context.space_combat_context.step != SpaceCombatStep.ANTI_FIGHTER_BARRAGE
            or state.turn_context.space_combat_context.round_number > 1
        ):
            return ValidationResult(
                is_valid=False,
                info="AFB is only usable during AFB step of first round of combat.",
            )
        if not state.player_may_resolve_afb_in_system(
            player_name=command.actor,
            system_id=get_active_system_id(state),
        ):
            return ValidationResult(
                is_valid=False,
                info="Player has no eligible units with ANTI-FIGHTER BARRAGE in the system.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [ResolveAntiFighterBarrageEvent(player_name=command.actor)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if state.turn_context.space_combat_context is None:
            return []
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=UseAntiFighterBarrageCommandRule,
        )


class PassAntiFighterBarrageCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassAntiFighterBarrageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_ANTI_FIGHTER_BARRAGE}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if not state.window_context.is_window_active(Window.ANTI_FIGHTER_BARRAGE):
            return ValidationResult(
                is_valid=False,
                info="Can only pass during Anti-fighter barrage step.",
            )
        if state.window_context.player_has_passed_on_window(
            player_name=command.actor,
            window=Window.ANTI_FIGHTER_BARRAGE,
        ):
            return ValidationResult(is_valid=False, info="You already passed on this window.")
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [PassAntiFighterBarrageEvent(player_name=command.actor)]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if state.turn_context.space_combat_context is None:
            return []
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=PassAntiFighterBarrageCommandRule,
        )


class EndAntiFighterBarrageStepEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            replace(
                previous_state.turn_context.get_space_combat_context(),
                step=SpaceCombatStep.ANNOUNCE_RETREATS,
            ),
        )

    def __repr__(self) -> str:
        return "EndAntiFighterBarrageStepEvent"


class CloseAntiFighterBarrageWindowEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolveAntiFighterBarrageEvent, PassAntiFighterBarrageEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if all(
            not state.player_may_resolve_afb_in_system(
                player_name=player_name,
                system_id=get_active_system_id(state),
            )
            for player_name in [
                state.turn_context.get_space_combat_context().attacker,
                state.turn_context.get_space_combat_context().defender,
            ]
        ):
            return [CloseWindowEvent(Window.ANTI_FIGHTER_BARRAGE), EndAntiFighterBarrageStepEvent()]
        return []


class AnnounceRetreatEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player = player_name

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().announce_retreat(
                player_name=self.player,
                is_retreating=True,
            ),
        )

    def __repr__(self) -> str:
        return "AnnounceRetreatEvent"


class PassAnnounceRetreatEvent(Event):
    def __init__(self, player_name: str) -> None:
        self.player_name = player_name

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().announce_retreat(
                player_name=self.player_name,
                is_retreating=False,
            ),
        )

    def __repr__(self) -> str:
        return "PassAnnounceRetreatEvent"


def _is_eligible_retreat_system_for_player(system, state: GameState, player_name: str) -> bool:
    if not state.get_active_system().is_adjacent_to(system):
        return False
    if any(
        ship.owner_name != player_name for ship in state.get_ships_in_system(system_id=system.id)
    ):
        return False
    return any(
        unit.owner_name == player_name for unit in state.get_units_in_system(system.id)
    ) or any(planet.controller == player_name for planet in system.planets)


def _check_for_eligible_retreat_system(state: GameState, player_name: str) -> ValidationResult:
    systems = state.galaxy.get_adjacent_systems(system_id=get_active_system_id(state))
    for system in systems:
        if _is_eligible_retreat_system_for_player(system, state=state, player_name=player_name):
            return ValidationResult(is_valid=True)
    return ValidationResult(is_valid=False, info="No legal retreat system found.")


def _check_declaration_ordering(
    state: GameState,
    command: Command,
    space_combat_context: SpaceCombatContext,
) -> ValidationResult:
    participant = state.turn_context.get_space_combat_context().get_participant_by_player(
        player_name=command.actor,
    )
    if (
        space_combat_context.retreat_declaration.get_declaration_by_participant(
            participant=participant,
        )
        is not None
    ):
        return ValidationResult(
            is_valid=False,
            info="This player has already passed/declared retreat this round.",
        )
    if participant == SpaceCombatParticipant.ATTACKER:
        if space_combat_context.retreat_declaration.defender_has_declared is None:
            return ValidationResult(
                is_valid=False,
                info="Must allow defender to declare retreats first.",
            )
        if (
            space_combat_context.retreat_declaration.defender_has_declared
            and command.command_type == CommandType.ANNOUNCE_RETREAT
        ):
            return ValidationResult(
                is_valid=False,
                info="Defender has already announced a retreat, attacker cannot.",
            )
    return ValidationResult(is_valid=True)


EventFactoryByPlayer = Callable[[str], Event]


class AnnounceRetreatCommandRule(CommandRule[Command]):
    _COMMAND_TO_EVENT_FACTORY: Final[dict[CommandType, EventFactoryByPlayer]] = {
        CommandType.ANNOUNCE_RETREAT: AnnounceRetreatEvent,
        CommandType.PASS_ANNOUNCE_RETREAT: PassAnnounceRetreatEvent,
    }

    @classmethod
    def _make_event_from_command(cls, command_type: CommandType, player_name: str) -> Event:
        return cls._COMMAND_TO_EVENT_FACTORY[command_type](player_name)

    def __repr__(self) -> str:
        return "AnnounceRetreatCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.ANNOUNCE_RETREAT, CommandType.PASS_ANNOUNCE_RETREAT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.turn_context.get_space_combat_context().step != SpaceCombatStep.ANNOUNCE_RETREATS:
            return ValidationResult(
                is_valid=False,
                info="Can only announce retreats in announce retreats step.",
            )
        space_combat_context = state.turn_context.get_space_combat_context()
        if command.actor not in (space_combat_context.attacker, space_combat_context.defender):
            return ValidationResult(
                is_valid=False,
                info="You are not participating in this combat.",
            )
        result = _check_declaration_ordering(
            state=state,
            command=command,
            space_combat_context=space_combat_context,
        )
        if not result.is_valid:
            return result
        if command.command_type == CommandType.PASS_ANNOUNCE_RETREAT:
            return ValidationResult(is_valid=True)
        return _check_for_eligible_retreat_system(state=state, player_name=command.actor)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [
            self._make_event_from_command(
                command_type=command.command_type,
                player_name=command.actor,
            ),
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if state.turn_context.space_combat_context is None:
            return []
        return make_command_candidates_for_all_players(
            state=state,
            command_rule=AnnounceRetreatCommandRule,
        )


class AdvanceToRollDiceStepEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            replace(
                previous_state.turn_context.get_space_combat_context(),
                step=SpaceCombatStep.ROLL_DICE,
            ),
        )

    def __repr__(self) -> str:
        return "AdvanceToRollDiceStepEvent"


class AdvanceToRetreatStepEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            replace(
                previous_state.turn_context.get_space_combat_context(),
                step=SpaceCombatStep.RETREAT,
            ),
        )

    def __repr__(self) -> str:
        return "AdvanceToRetreatStepEvent"


class AdvanceToRollDiceStepEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        combat_context = state.turn_context.get_space_combat_context()
        if (
            combat_context.declared_retreat_name is not None
            or combat_context.retreat_declaration.both_players_have_responded
        ):
            return [AdvanceToRollDiceStepEvent()]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {PassAnnounceRetreatEvent, AnnounceRetreatEvent}


@dataclass(frozen=True)
class RetreatShipCommand(Command):
    ship_id: int
    to_system_id: int
    transported_unit_ids: frozenset[int] = frozenset()


def _ship_is_valid_for_retreat(
    ship: Ship,
    command: RetreatShipCommand,
    state: GameState,
) -> ValidationResult:
    if ship.system_id != get_active_system_id(state):
        return ValidationResult(
            is_valid=False,
            info=f"{command.ship_id} is not in the active system.",
        )
    if ship.stats.move is None:
        return ValidationResult(
            is_valid=False,
            info=f"{command.ship_id} cannot move on its own.",
        )
    if ship.unit_id in {move.unit_id for move in state.turn_context.pending_moves}:
        return ValidationResult(
            is_valid=False,
            info=f"This ship {ship.unit_id} already declared retreat.",
        )
    return ValidationResult(is_valid=True)


class RetreatShipCommandRule(CommandRule[RetreatShipCommand]):
    def __repr__(self) -> str:
        return "RetreatShip"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.RETREAT_SHIP}

    def validate_legality(self, state: GameState, command: RetreatShipCommand) -> ValidationResult:
        context = state.turn_context.get_space_combat_context()
        if context.step != SpaceCombatStep.RETREAT:
            return ValidationResult(
                is_valid=False,
                info="Can only retreat during the retreat step.",
            )
        if context.declared_retreat_name != command.actor:
            return ValidationResult(
                is_valid=False,
                info="Only the player who declared may retreat.",
            )
        if not _is_eligible_retreat_system_for_player(
            system=state.galaxy.get_system(command.to_system_id),
            state=state,
            player_name=command.actor,
        ):
            return ValidationResult(
                is_valid=False,
                info="System is not eligible for retreat: must contain one or more of that player's"
                " units, a planet they control, or both, as well as no ships controlled by another "
                "player.",
            )
        ship = state.get_ship_from_id(ship_id=command.ship_id)
        return _ship_is_valid_for_retreat(ship=ship, command=command, state=state)

    def derive_events(
        self,
        state: GameState,
        command: RetreatShipCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, engine_context
        return [
            AddMoveToPendingEvent(
                unit_id=command.ship_id,
                to_system_id=command.to_system_id,
            ),
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[RetreatShipCommand]:
        if state.turn_context.space_combat_context is None:
            return []
        retreating_player_name = state.turn_context.get_space_combat_context().declared_retreat_name
        if retreating_player_name is None:
            return []
        eligible_systems = {
            system
            for system in state.galaxy
            if _is_eligible_retreat_system_for_player(
                system=system,
                state=state,
                player_name=retreating_player_name,
            )
        }
        return [
            RetreatShipCommand(
                actor=retreating_player_name,
                command_type=CommandType.RETREAT_SHIP,
                ship_id=ship.unit_id,
                to_system_id=system.id,
            )
            for ship in state.get_ships_in_system(get_active_system_id(state))
            if ship.owner_name == retreating_player_name
            for system in eligible_systems
        ]


def resolve_pending_retreats(previous_state: GameState) -> GameState:
    destination_systems = {move.to_system_id for move in previous_state.turn_context.pending_moves}
    if len(destination_systems) != 1:
        raise InvalidRetreatError
    new_state = resolve_pending_moves(previous_state=previous_state)
    return replace(
        new_state,
        turn_context=new_state.turn_context.set_retreat_system_id(destination_systems.pop()),
    )


class ResolvePendingRetreatsEvent(Event):
    def __repr__(self) -> str:
        return "ResolvePendingRetreatsEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return resolve_pending_retreats(previous_state=previous_state)


class EndRetreatCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "EndRetreat"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_RETREAT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.turn_context.get_space_combat_context().step != SpaceCombatStep.RETREAT:
            return ValidationResult(
                is_valid=False,
                info="Can only retreat during the retreat step.",
            )
        if state.turn_context.get_space_combat_context().declared_retreat_name != command.actor:
            return ValidationResult(
                is_valid=False,
                info="Only the retreating player may resolve retreats.",
            )
        ships_in_active_system_with_move_value = {
            ship.unit_id
            for ship in state.get_ships_in_system(
                system_id=get_active_system_id(state),
                player_name=command.actor,
            )
            if ship.stats.move is not None
        }
        pending_retreats = {move.unit_id for move in state.turn_context.pending_moves}
        if len(ships_in_active_system_with_move_value - pending_retreats) > 0:
            return ValidationResult(
                is_valid=False,
                info="You must retreat all ships with a move value.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: Command,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del state, command, engine_context
        return [ResolvePendingRetreatsEvent()]

    @staticmethod
    def candidate_commands(state: GameState) -> list[Command]:
        if state.turn_context.space_combat_context is None:
            return []
        retreating_player_name = state.turn_context.get_space_combat_context().declared_retreat_name
        if retreating_player_name is None:
            return []
        return [
            Command(
                actor=retreating_player_name,
                command_type=CommandType.END_RETREAT,
            ),
        ]


class RemoveAbandonedFightersAndGroundForcesEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        abandoned_units = state.get_units_in_space_area_of_system(
            system_id=get_active_system_id(state),
            player_name=state.turn_context.get_space_combat_context().declared_retreat_name,
        )
        return [RemoveUnitEvent(unit_id=unit.unit_id) for unit in abandoned_units]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolvePendingRetreatsEvent}


class PlaceCommandTokenFromPoolEvent(Event):
    def __init__(self, system_id: int, pool: CommandTokenPool) -> None:
        self.system_id = system_id
        self.pool = pool

    def apply(self, previous_state: GameState) -> GameState:
        retreating_player_name = (
            previous_state.turn_context.get_space_combat_context().declared_retreat_name
        )
        if retreating_player_name is None:
            raise ValueError
        return previous_state.withdraw_command_token(
            player_name=retreating_player_name,
            from_pool=self.pool,
        ).place_command_token_in_system(
            player_name=retreating_player_name,
            system_id=self.system_id,
        )

    def __repr__(self) -> str:
        return f"PlaceCommandTokenFromPoolEvent:{self.system_id}:{self.pool}"


class PlaceCommandTokenInDestinationSystemIfAbleEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        retreating_player_name = state.turn_context.get_space_combat_context().declared_retreat_name
        if retreating_player_name is None:
            raise InvalidRetreatError
        command_sheet = state.get_player(retreating_player_name).command_sheet
        if len(command_sheet.reinforcements) < 1:
            return [OpenWindowEvent(Window.MUST_CHOOSE_POOL_FOR_REMOVE_COMMAND_TOKEN)]
        return [
            PlaceCommandTokenFromPoolEvent(
                system_id=state.turn_context.get_retreat_system_id(),
                pool=CommandTokenPool.REINFORCEMENTS,
            ),
        ]

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {ResolvePendingRetreatsEvent}


@dataclass(frozen=True)
class RemoveCommandTokenFromPoolCommand(Command):
    pool: CommandTokenPool


class ChoosePoolToRemoveCommandTokenCommandRule(CommandRule[RemoveCommandTokenFromPoolCommand]):
    def __repr__(self) -> str:
        return "ChoosePoolToRemoveCommandTokenCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.REMOVE_COMMAND_TOKEN_FROM_POOL}

    def validate_legality(
        self,
        state: GameState,
        command: RemoveCommandTokenFromPoolCommand,
    ) -> ValidationResult:
        if not state.window_context.is_window_active(
            Window.MUST_CHOOSE_POOL_FOR_REMOVE_COMMAND_TOKEN,
        ):
            return ValidationResult(
                is_valid=False,
                info="Can only remove token from pool in proper window.",
            )
        retreating_player_name = state.turn_context.get_space_combat_context().declared_retreat_name
        if retreating_player_name is None:
            raise InvalidRetreatError
        if retreating_player_name != command.actor:
            return ValidationResult(
                is_valid=False,
                info="Only the relevant player may choose a pool.",
            )
        if (
            len(state.get_player(retreating_player_name).command_sheet.get_pool(pool=command.pool))
            < 1
        ):
            return ValidationResult(
                is_valid=False,
                info=f"You have no tokens in {command.pool.value}.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(
        self,
        state: GameState,
        command: RemoveCommandTokenFromPoolCommand,
        engine_context: EngineContext,
    ) -> Sequence[Event]:
        del engine_context
        return [
            CloseWindowEvent(window=Window.MUST_CHOOSE_POOL_FOR_REMOVE_COMMAND_TOKEN),
            PlaceCommandTokenFromPoolEvent(
                system_id=state.turn_context.get_retreat_system_id(),
                pool=command.pool,
            ),
        ]

    @staticmethod
    def candidate_commands(state: GameState) -> list[RemoveCommandTokenFromPoolCommand]:
        if state.turn_context.space_combat_context is None:
            return []
        return [
            RemoveCommandTokenFromPoolCommand(
                actor=player.name,
                command_type=CommandType.REMOVE_COMMAND_TOKEN_FROM_POOL,
                pool=pool,
            )
            for player, pool in itertools.product(state.players, CommandTokenPool)
        ]


class ResetCombatToAnnounceRetreatStepEvent(Event):
    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.reset_combat_round()

    def __repr__(self) -> str:
        return "ResetCombatToAnnounceRetreatStepEvent"
