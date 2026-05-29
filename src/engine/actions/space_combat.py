from dataclasses import replace
from typing import TYPE_CHECKING, Callable, Final

from src.engine.actions.movement import EndMovementStepEvent, OpenWindowEvent
from src.engine.actions.tactical_action import (
    AdvanceToInvasionStepEvent,
    AdvanceToSpaceCombatStepEvent,
)
from src.engine.core.command import Command, CommandRule, CommandType, ValidationResult
from src.engine.core.event import Event, EventRule
from src.engine.core.game_state import (
    Ability,
    GameState,
    SpaceCombatContext,
    SpaceCombatParticipant,
    SpaceCombatStep,
    TacticalActionStep,
    Window,
)
from src.engine.core.player import Player
from src.engine.core.windows import CloseWindowEvent

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.system import System


START_OF_COMBAT_ROUND_WINDOWS: list[Window] = [
    Window.START_OF_SPACE_COMBAT,
    Window.START_OF_FIRST_ROUND_OF_SPACE_COMBAT,
    Window.START_OF_SPACE_COMBAT_ROUND,
]


class StartSpaceCombatEvent(Event):
    def __repr__(self) -> str:
        return "StartSpaceCombatEvent"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            space_combat_context=SpaceCombatContext(
                step=SpaceCombatStep.ANTI_FIGHTER_BARRAGE,
                round_number=1,
                attacker=previous_state.active_player,
                defender=previous_state.get_defender_in_system(
                    system_id=previous_state.get_active_system().id,
                ),
            ),
        )


class OpenStartOfSpaceCombatWindowEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {AdvanceToSpaceCombatStepEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event, state
        return [
            StartSpaceCombatEvent(),
        ] + [OpenWindowEvent(window=window) for window in START_OF_COMBAT_ROUND_WINDOWS]


class SkipSpaceCombatIfOnlyOnePlayerHasShips(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {EndMovementStepEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if (
            len(
                {
                    unit.owner_name
                    for unit in state.get_ships_in_system(state.get_active_system().id)
                },
            )
            <= 1
        ):
            return [AdvanceToInvasionStepEvent()]
        return [AdvanceToSpaceCombatStepEvent()]


class EndSpaceCombatCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "EndSpaceCombatCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_SPACE_COMBAT}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        if state.active_player != command.actor:
            return ValidationResult(is_valid=False, info="Only active player can end space combat.")
        if state.turn_context.tactical_action_step != TacticalActionStep.SPACE_COMBAT:
            return ValidationResult(
                is_valid=False,
                info="Can only end space combat during space combat window.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> list[Event]:
        del state, command
        return [AdvanceToInvasionStepEvent()]


class DestroyUnitEvent(Event):
    def __init__(self, unit_id: int) -> None:
        self.unit_id = unit_id

    def __repr__(self) -> str:
        return f"DestroyUnitEvent(unit_id={self.unit_id})"

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.resolve_assigned_hit(unit_id=self.unit_id)


class EndAssignHitsCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "EndAssignHitsCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.END_ASSIGN_HITS}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del command

        return [DestroyUnitEvent(unit_id) for unit_id in state.get_pending_assigned_hits()]


class EndSpaceCombatEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {DestroyUnitEvent, EndAntiFighterBarrageStepEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if state.turn_context.tactical_action_step != TacticalActionStep.SPACE_COMBAT:
            return []
        if (
            len(
                {
                    ship.owner_name
                    for ship in state.get_ships_in_system(state.get_active_system().id)
                },
            )
            <= 1
        ) and (len(state.turn_context.get_space_combat_context().assigned_hits) == 0):
            return [
                OpenWindowEvent(window=Window.END_OF_SPACE_COMBAT),
                OpenWindowEvent(window=Window.END_OF_SPACE_COMBAT_ROUND),
            ]
        return []


class PassStartOfCombatWindowCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassStartOfCombatWindowCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_START_OF_COMBAT_ROUND}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state
        return [PassStartOfCombatWindowEvent(player=command.actor)]


class PassStartOfCombatWindowEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def __repr__(self) -> str:
        return f"PassStartOfCombatWindowEvent:{self.player}"

    def apply(self, previous_state: GameState) -> GameState:
        active_state = previous_state
        for window in previous_state.window_context.active_windows:
            if window in START_OF_COMBAT_ROUND_WINDOWS:
                active_state = active_state.pass_on_window_for_player(
                    player=self.player,
                    window=window,
                )
        return active_state


class CloseStartOfSpaceCombatRoundWindowsEventRule(EventRule):
    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {PassStartOfCombatWindowEvent}

    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        if all(
            state.window_context.player_has_passed_on_window(
                player,
                window=Window.START_OF_SPACE_COMBAT_ROUND,
            )
            for player in state.players
        ):
            return [
                CloseWindowEvent(window=window)
                for window in state.window_context.active_windows
                if window in START_OF_COMBAT_ROUND_WINDOWS
            ] + [OpenWindowEvent(window=Window.ANTI_FIGHTER_BARRAGE)]
        return []


class ResolveAntiFighterBarrageEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.use_ability_for_player(
            player=self.player,
            ability=Ability.ANTI_FIGHTER_BARRAGE,
        )

    def __repr__(self) -> str:
        return f"ResolveAntiFighterBarrageEvent:{self.player}"


class PassAntiFighterBarrageEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.pass_on_window_for_player(
            player=self.player,
            window=Window.ANTI_FIGHTER_BARRAGE,
        )

    def __repr__(self) -> str:
        return f"PassAntiFighterBarrageEvent:{self.player}"


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
            player=command.actor,
            system_id=state.get_active_system().id,
        ):
            return ValidationResult(
                is_valid=False,
                info="Player has no eligible units with ANTI-FIGHTER BARRAGE in the system.",
            )
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state
        return [ResolveAntiFighterBarrageEvent(player=command.actor)]


class PassAntiFighterBarrageCommandRule(CommandRule[Command]):
    def __repr__(self) -> str:
        return "PassAntiFighterBarrageCommandRule"

    @staticmethod
    def handles_command_types() -> set[CommandType]:
        return {CommandType.PASS_ANTI_FIGHTER_BARRAGE}

    def validate_legality(self, state: GameState, command: Command) -> ValidationResult:
        del state, command
        return ValidationResult(is_valid=True)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state
        return [PassAntiFighterBarrageEvent(player=command.actor)]


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
                player=player,
                system_id=state.get_active_system().id,
            )
            for player in [
                state.turn_context.get_space_combat_context().attacker,
                state.turn_context.get_space_combat_context().defender,
            ]
        ):
            return [CloseWindowEvent(Window.ANTI_FIGHTER_BARRAGE), EndAntiFighterBarrageStepEvent()]
        return []


class AnnounceRetreatEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().announce_retreat(
                player=self.player,
                is_retreating=True,
            ),
        )

    def __repr__(self) -> str:
        return "AnnounceRetreatEvent"


class PassAnnounceRetreatEvent(Event):
    def __init__(self, player: Player) -> None:
        self.player = player

    def apply(self, previous_state: GameState) -> GameState:
        return previous_state.set_space_combat_context(
            previous_state.turn_context.get_space_combat_context().announce_retreat(
                player=self.player,
                is_retreating=False,
            ),
        )

    def __repr__(self) -> str:
        return "PassAnnounceRetreatEvent"


def _is_eligible_retreat_system(system: System, state: GameState) -> bool:
    if not state.get_active_system().is_adjacent_to(system):
        return False
    if any(
        ship.owner_name != state.active_player.name
        for ship in state.get_ships_in_system(system_id=system.id)
    ):
        return False
    return any(
        unit.owner_name == state.active_player.name for unit in state.get_units_in_system(system.id)
    ) or any(planet.controller == state.active_player for planet in system.planets)


def _check_for_eligible_retreat_system(state: GameState) -> ValidationResult:
    systems = state.galaxy.get_adjacent_systems(system_id=state.get_active_system().id)
    for system in systems:
        if _is_eligible_retreat_system(system, state=state):
            return ValidationResult(is_valid=True)
    return ValidationResult(is_valid=False, info="No legal retreat system found.")


def _check_declaration_ordering(
    state: GameState,
    command: Command,
    space_combat_context: SpaceCombatContext,
) -> ValidationResult:
    participant = state.turn_context.get_space_combat_context().get_participant_by_player(
        player=command.actor,
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


EventFactoryByPlayer = Callable[[Player], Event]


class AnnounceRetreatCommandRule(CommandRule[Command]):
    _COMMAND_TO_EVENT_FACTORY: Final[dict[CommandType, EventFactoryByPlayer]] = {
        CommandType.ANNOUNCE_RETREAT: AnnounceRetreatEvent,
        CommandType.PASS_ANNOUNCE_RETREAT: PassAnnounceRetreatEvent,
    }

    @classmethod
    def _make_event_from_command(cls, command_type: CommandType, player: Player) -> Event:
        return cls._COMMAND_TO_EVENT_FACTORY[command_type](player)

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

        return _check_for_eligible_retreat_system(state=state)

    def derive_events(self, state: GameState, command: Command) -> Sequence[Event]:
        del state
        return [
            self._make_event_from_command(command_type=command.command_type, player=command.actor),
        ]


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


class AdvanceToRollDiceStepEventRule(EventRule):
    def on_event(self, state: GameState, event: Event) -> Sequence[Event]:
        del event
        combat_context = state.turn_context.get_space_combat_context()
        if (
            combat_context.declared_retreat is not None
            or combat_context.retreat_declaration.both_players_have_responded
        ):
            return [AdvanceToRollDiceStepEvent()]
        return []

    @staticmethod
    def handles_event_types() -> set[type[Event]]:
        return {PassAnnounceRetreatEvent, AnnounceRetreatEvent}


def get_command_rules() -> list[CommandRule[Command]]:
    return [
        EndSpaceCombatCommandRule(),
        EndAssignHitsCommandRule(),
        UseAntiFighterBarrageCommandRule(),
        PassAntiFighterBarrageCommandRule(),
        PassStartOfCombatWindowCommandRule(),
        AnnounceRetreatCommandRule(),
    ]


def get_event_rules() -> list[EventRule]:
    return [
        OpenStartOfSpaceCombatWindowEventRule(),
        SkipSpaceCombatIfOnlyOnePlayerHasShips(),
        EndSpaceCombatEventRule(),
        CloseStartOfSpaceCombatRoundWindowsEventRule(),
        CloseAntiFighterBarrageWindowEventRule(),
        AdvanceToRollDiceStepEventRule(),
    ]
