from typing import TYPE_CHECKING

from src.engine.core.game_engine import GameStateInvariant
from src.engine.core.player import MAX_COMMAND_TOKENS
from src.engine.tokens import UNIQUE_TOKENS, TokenType

if TYPE_CHECKING:
    from src.engine.core.game_state import GameState


class UniqueTokenInvariant(GameStateInvariant):
    description = (
        """A token which can exist only once in the game must be unique across all players."""
    )

    def __init__(self, tokens: set[TokenType]) -> None:
        self.tokens: set[TokenType] = tokens

    def check(self, state: GameState) -> bool:
        seen_tokens: set[TokenType] = set()
        for player in state.players:
            for token in player.play_area:
                if token not in self.tokens:
                    continue
                if token in seen_tokens:
                    return False
                seen_tokens.add(token)
        return True


class NoPassedPlayersWithReadyStrategyCards(GameStateInvariant):
    description = """Players can never be passed and also have ready strategy cards."""

    def check(self, state: GameState) -> bool:
        for player in state.players:
            if player.has_passed and any(card.is_ready for card in player.strategy_cards):
                return False
        return True


class UnitOnPlanetImpliesUnitInSystem(GameStateInvariant):
    description = """Units which are on a planet are also in the planet's system."""

    def check(self, state: GameState) -> bool:
        planet_to_system_map: dict[int, int] = {}
        for system in state.galaxy:
            planet_to_system_map |= {planet.planet_id: system.id for planet in system.planets}
        ground_forces = {
            unit.cast_to_ground_force() for unit in state.units if unit.is_ground_force
        }
        for unit in ground_forces:
            if unit.planet_id is not None and (
                unit.planet_id not in planet_to_system_map
                or planet_to_system_map[unit.planet_id] != unit.system_id
            ):
                return False
        return True


class EachPlayerHasExactly16CommandTokens(GameStateInvariant):
    description = """Across the entire game state, each player should have exactly 16 tokens."""

    def check(self, state: GameState) -> bool:
        for player in state.players:
            total_command_tokens = (
                len(player.command_sheet.tactic)
                + len(player.command_sheet.fleet)
                + len(player.command_sheet.strategy)
                + len(player.command_sheet.reinforcements)
            ) + sum(1 for system in state.galaxy if system.has_command_token(player))
            if total_command_tokens != MAX_COMMAND_TOKENS:
                return False
        return True


def make_all_invariants() -> list[GameStateInvariant]:
    return [
        UniqueTokenInvariant(tokens=UNIQUE_TOKENS),
        NoPassedPlayersWithReadyStrategyCards(),
        UnitOnPlanetImpliesUnitInSystem(),
        EachPlayerHasExactly16CommandTokens(),
    ]
