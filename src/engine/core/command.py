import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.engine.core.event import Event
    from src.engine.core.game_engine import DiceRoller
    from src.engine.core.game_state import GameState


class CommandType(enum.StrEnum):
    END_TURN = "end_turn"
    ALWAYS_VALID = "always_valid"
    ALWAYS_INVALID = "always_invalid"
    INITIATE_TACTICAL_ACTION = "initiate_tactical_action"
    PASS_ACTION = "pass_action"
    END_MOVEMENT = "end_movement"
    MOVE_SHIP = "move_ship"
    COMMIT_GROUND_FORCE = "commit_ground_force"
    USE_SPACE_CANNON = "use_space_cannon"
    PASS_SPACE_CANNON = "pass_space_cannon"
    USE_BOMBARDMENT = "use_bombardment"
    PASS_BOMBARDMENT = "pass_bombardment"
    END_INVASION = "end_invasion"
    USE_PRODUCTION = "use_production"
    PASS_PRODUCTION = "pass_production"
    USE_ANTI_FIGHTER_BARRAGE = "use_anti_fighter_barrage"
    PASS_ANTI_FIGHTER_BARRAGE = "pass_anti_fighter_barrage"
    PASS_START_OF_COMBAT_ROUND = "pass_start_of_combat_round"
    ANNOUNCE_RETREAT = "announce_retreat"
    PASS_ANNOUNCE_RETREAT = "pass_announce_retreat"
    MAKE_COMBAT_ROLLS = "make_combat_rolls"
    ASSIGN_HIT = "assign_hit"
    PASS_BEFORE_ASSIGN_HITS = "pass_before_assign_hits"
    USE_SUSTAIN_DAMAGE = "use_sustain_damage"
    RETREAT_SHIP = "retreat_ship"
    END_RETREAT = "end_retreat"
    REMOVE_COMMAND_TOKEN_FROM_POOL = "remove_command_token_from_pool"
    PASS_END_OF_COMBAT_ROUND = "pass_end_of_combat_round"
    REMOVE_UNIT = "remove_unit"
    TRANSPORT_UNIT = "transport_unit"
    PASS_TRANSPORT_UNIT = "pass_transport_unit"

    @staticmethod
    def all_command_types() -> list[CommandType]:
        return list(CommandType.__members__.values())


@dataclass(frozen=True)
class Command:
    actor: str
    command_type: CommandType


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    info: str = ""


@dataclass(frozen=True)
class EngineContext:
    dice_roller: DiceRoller


CommandT = TypeVar("CommandT", bound=Command)


class CommandRule[C: Command](Protocol):
    def __repr__(self) -> str: ...
    @staticmethod
    def handles_command_types() -> set[CommandType]: ...
    def validate_legality(self, state: GameState, command: C) -> ValidationResult: ...
    def derive_events(
        self,
        state: GameState,
        command: C,
        engine_context: EngineContext,
    ) -> Sequence[Event]: ...
    @staticmethod
    def candidate_commands(state: GameState) -> list[C]: ...


def make_command_candidates_for_all_players(
    state: GameState,
    command_rule: type[CommandRule[Command]],
) -> list[Command]:
    return [
        Command(actor=player.name, command_type=cmd_type)
        for player in state.players
        for cmd_type in command_rule.handles_command_types()
    ]
