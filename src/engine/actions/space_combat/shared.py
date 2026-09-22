from src.engine.core.game_state import GameState, Window

START_OF_COMBAT_ROUND_WINDOWS: list[Window] = [
    Window.START_OF_SPACE_COMBAT,
    Window.START_OF_FIRST_ROUND_OF_SPACE_COMBAT,
    Window.START_OF_SPACE_COMBAT_ROUND,
]

END_OF_COMBAT_ROUND_WINDOWS: list[Window] = [
    Window.END_OF_SPACE_COMBAT,
    Window.END_OF_SPACE_COMBAT_ROUND,
]


def get_active_system_id(state: GameState) -> int:
    return state.get_active_system().id


def active_ship_owners(state: GameState) -> set[str]:
    return {unit.owner_name for unit in state.get_ships_in_system(get_active_system_id(state))}


def needs_to_assign_hits(state: GameState, player_name: str) -> bool:
    combat = state.turn_context.get_space_combat_context()
    hits = combat.total_hits_for_player(combat.opponent_of(player_name))
    return hits > 0 and bool(state.get_ships_in_system(get_active_system_id(state), player_name))


def has_finished_assigning_hits(state: GameState, player_name: str) -> bool:
    if not needs_to_assign_hits(state=state, player_name=player_name):
        return True
    hit_context = state.turn_context.hit_assignment_context
    if hit_context is None:
        msg = f"Hit assignment required for {player_name}, but no hit assignment context exists."
        raise RuntimeError(msg)
    if hit_context.assignee != player_name:
        combat_context = state.turn_context.get_space_combat_context()
        return (
            player_name == combat_context.attacker
            and hit_context.assignee == combat_context.defender
        )
    return (hit_context.hits_remaining == 0) or not state.get_ships_in_system(
        system_id=get_active_system_id(state),
        player_name=player_name,
    )
