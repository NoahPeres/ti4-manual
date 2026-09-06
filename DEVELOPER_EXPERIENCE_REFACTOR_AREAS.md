# Developer Experience Refactor Areas

## 1. Standardize Major Action Modules

- **Implementation**: Package each major action under `src/engine/actions/<action>/` with a consistent shape such as `shared.py`, `opening.py`, `resolution.py`, and `cleanup.py`; keep `__init__.py` as the single registration/export surface.
- **DX impact**: New features land in an obvious file, developers copy an existing pattern instead of inventing structure, and tests can target one phase/module at a time.

## 2. Shrink `GameState` To State + Primitive Helpers

- **Implementation**: Move phase-specific query logic out of `src/engine/core/game_state.py` into focused modules or views like `combat_queries.py`, `movement_queries.py`, or `CombatView`.
- **Code shape**:

```python
@dataclass(frozen=True)
class GameState:
    players: tuple[Player, ...]
    systems: Galaxy
    turn_context: TurnContext

    def replace_system(self, system: System) -> "GameState":
        ...
```

```python
def get_combat_participants(state: GameState) -> tuple[str, str]:
    system_id = state.turn_context.active_system_id
    ships = state.get_ships_in_system(system_id)
    ...


def remaining_hits_for_player(state: GameState, player_name: str) -> int:
    ...
```

```python
class AssignHitCommandRule(CommandRule[AssignHitCommand]):
    def validate_legality(self, state: GameState, command: AssignHitCommand) -> ValidationResult:
        if combat_queries.remaining_hits_for_player(state, command.actor) == 0:
            return ValidationResult(is_valid=False, info="No more hits to assign.")
        ...
```
- **DX impact**: Feature code stops digging through a god object, state transitions become easier to reason about, and tests can exercise small query units without building full game scenarios.

## 3. Make Windows Declarative

- **Implementation**: Introduce a reusable window definition model, e.g. `WindowDefinition(open_event, pass_command, close_condition, next_events)`, and let actions register window flows instead of hand-writing open/pass/close rules each time.
- **Code shape**:

```python
@dataclass(frozen=True)
class WindowDefinition:
    window: Window
    opens_on: type[Event]
    pass_command_type: CommandType
    closes_when: Callable[[GameState], bool]
    next_events: Callable[[GameState], Sequence[Event]]
```

```python
SPACE_COMBAT_WINDOWS = [
    WindowDefinition(
        window=Window.START_OF_SPACE_COMBAT_ROUND,
        opens_on=StartSpaceCombatEvent,
        pass_command_type=CommandType.PASS_START_OF_COMBAT_ROUND,
        closes_when=all_players_passed(Window.START_OF_SPACE_COMBAT_ROUND),
        next_events=lambda state: [OpenWindowEvent(Window.ANTI_FIGHTER_BARRAGE)],
    ),
]
```

```python
def get_window_rules(definition: WindowDefinition) -> list[EventRule | CommandRule]:
    return [
        OpenWindowRule(definition),
        PassWindowRule(definition),
        CloseWindowRule(definition),
    ]
```
- **DX impact**: Adding a new timing window becomes configuration-like work, rule ordering is easier to audit, and duplicated edge-case logic drops sharply.

## 4. Add Phase-Scoped Read Models

- **Implementation**: Add immutable read models such as `CombatView(state)` and `MovementView(state)` that precompute common lookups: active system, participants, eligible units, remaining hits, legal retreat systems.
- **Code shape**:

```python
@dataclass(frozen=True)
class CombatView:
    state: GameState

    @cached_property
    def system_id(self) -> int:
        return self.state.turn_context.active_system_id

    @cached_property
    def participants(self) -> tuple[str, str]:
        return combat_queries.get_combat_participants(self.state)

    @cached_property
    def ships_by_player(self) -> dict[str, tuple[Ship, ...]]:
        ...

    def needs_hit_assignment(self, player_name: str) -> bool:
        ...

    def legal_retreat_systems(self, player_name: str) -> tuple[System, ...]:
        ...
```

```python
class RetreatShipCommandRule(CommandRule[RetreatShipCommand]):
    def validate_legality(self, state: GameState, command: RetreatShipCommand) -> ValidationResult:
        combat = CombatView(state)
        if command.to_system_id not in {system.id for system in combat.legal_retreat_systems(command.actor)}:
            return ValidationResult(is_valid=False, info="Illegal retreat destination.")
        ...
```
- **DX impact**: Rule code becomes shorter and more local, developers stop repeating traversal logic, and tests can assert on one view object instead of re-deriving state in every test.

## 5. Move Toward Replay/Fixture-Driven Tests

- **Implementation**: Keep end-to-end scenario tests, but add small phase fixtures plus replay helpers built on command/event history in `game_session`; organize tests by phase, not only by large LRR scenario.
- **Code shape**:

```python
@dataclass(frozen=True)
class CombatFixture:
    state: GameState
    attacker: str
    defender: str


def make_basic_space_combat_fixture() -> CombatFixture:
    return CombatFixture(
        state=...,
        attacker="Player 1",
        defender="Player 2",
    )
```

```python
def replay_commands(session: GameSession, commands: Sequence[Command]) -> GameSession:
    for command in commands:
        session = session.apply_command(command)
    return session
```

```python
def test_assign_hits_advances_to_retreat_step() -> None:
    fixture = make_basic_space_combat_fixture()
    session = GameSession.from_state(fixture.state)
    session = replay_commands(session, [
        Command(... MAKE_COMBAT_ROLLS ...),
        AssignHitCommand(...),
    ])
    assert session.state.turn_context.space_combat_context.step == SpaceCombatStep.RETREAT
```

```python
def test_space_combat_replay_matches_expected_event_sequence() -> None:
    session = replay_commands(GameSession.from_state(...), commands)
    assert session.event_history == expected_events
```
- **DX impact**: New features get faster, more targeted tests, failures are easier to localize, and refactors can preserve behavior with smaller golden/replay checks instead of only heavyweight scenarios.

## 6. Reuse One Rule Wiring Pattern Everywhere

- **Implementation**: For each subsystem, expose `get_command_rules()` and `get_event_rules()` from one package entrypoint and keep internal modules private by default.
- **DX impact**: Registration stays predictable, imports stay shallow, and moving code between files does not create repo-wide churn.
