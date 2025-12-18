# Design Ethos for a Robust Board Game Engine

## Purpose of This Document

This document consolidates the recommended architectural principles, design constraints, and structural patterns for implementing a complex, highly interactive board game engine. It is intended as a *foundational reference* to guide development from a minimal prototype to a fully featured, AI-compatible system without requiring architectural rewrites.

The ethos prioritizes:

* Correctness over convenience
* Determinism over implicit behavior
* Explicit orchestration over emergent side effects
* Long-term extensibility over early optimization

---

## 1. Core Philosophical Principles

### 1.1 The Game Is a Deterministic State Machine

The game engine is fundamentally a deterministic state transition system:

```
(GameState, Action) -> GameState | Failure
```

Implications:

* All game-relevant information must reside in `GameState`
* State transitions are deterministic and reproducible
* Randomness is injected only via explicit, state-contained seeds
* No mutation occurs outside controlled transitions

This model enables undo, replay, auditing, and AI training.

---

### 1.2 Single Source of Truth

There is exactly **one authoritative game state** at any moment.

* UI, networking, AI, and persistence layers are consumers
* No component is permitted to mutate state directly
* All state changes pass through the same engine interface

---

### 1.3 Actions Express Intent, Events Express Fact

* **Actions** represent player or system intent
* **Events** represent facts that have occurred

Rules:

* Actions never mutate state
* Actions are validated against the current state
* Valid actions produce zero or more events
* Events are the only mechanism that transforms state

---

## 2. Atomicity, Undo, and Safety

### 2.1 Atomic State Transitions

Every action is processed as a transaction:

1. Validate action
2. Derive events
3. Apply events to produce a candidate state
4. Validate global invariants
5. Commit or discard

If any step fails, the original state remains intact.

---

### 2.2 Immutable or Persistent State

GameState should be treated as immutable:

* New states are derived, never modified in place
* Structural sharing is preferred where available

Benefits:

* Guaranteed rollback
* Safe concurrency
* Easy debugging and replay

---

### 2.3 Event Sourcing

State evolution is driven by an append-only event log.

Advantages:

* Undo via event rewind
* Full replay capability
* Natural audit trail
* Excellent compatibility with AI training pipelines

---

## 3. Separation of Concerns

### 3.1 Core Engine (Pure Logic)

Responsibilities:

* Action validation
* Event derivation
* Event application
* Invariant enforcement

Constraints:

* No UI logic
* No networking
* No persistence
* No randomness outside state-contained RNG

---

### 3.2 Orchestrator / Controller

Responsibilities:

* Owns the authoritative state
* Accepts actions from external systems
* Applies actions atomically via the engine
* Manages undo/redo and history

---

### 3.3 Adapters

Examples:

* User interface
* Network protocol
* AI agents
* Replay/export tooling

Adapters may *query* state but never mutate it.

---

## 4. Turn Structure and Timing

### 4.1 Explicit Turn and Phase Modeling

Turn order, priority, and response windows must be explicitly represented in state:

* Active player
* Phase or step
* Allowed actions
* Pending triggers

Implicit timing is forbidden.

---

### 4.2 Interactive Response Windows

If the game allows reactions or interrupts:

* Represent them as explicit substates
* Restrict allowable actions accordingly
* Resolve responses sequentially and atomically

---

## 5. Ability System Ethos

### 5.1 Declarative Abilities

Abilities are data-driven rules, not procedural code paths.

An ability defines:

* Trigger condition
* Optional prerequisites
* Effect(s)
* Scope and duration

Abilities *produce events*; they do not mutate state directly.

---

### 5.2 Passive Modifiers

Passive abilities:

* Modify how values are computed
* Are evaluated at query time or resolution time
* Do not eagerly mutate state unless required

---

## 6. Determinism and AI Compatibility

To support AI, simulations, and LLM agents:

* All randomness must be seeded and stored
* No hidden state
* No wall-clock or timing dependencies
* Identical inputs must yield identical outputs

This enables:

* Massive parallel rollouts
* Reinforcement learning
* Strategy discovery

---

## 7. Testing and Verification

### 7.1 Invariant-Based Testing

Define and enforce global invariants:

* Exactly one active player
* No illegal resource values
* Valid board topology

Check invariants after every transition.

---

### 7.2 Replay and Regression Testing

* Maintain canonical event logs
* Ensure engine changes replay identically
* Treat replays as golden test cases

---

## 8. Guiding Rule (Non-Negotiable)

> **Rules do not mutate state. Rules produce events. Events mutate state.**

Violating this principle leads to non-determinism, broken undo, and unmaintainable complexity.

---

# Language and Tooling Comparison

## Evaluation Criteria

* Determinism and safety
* Support for immutability
* Performance under simulation
* Tooling for testing and profiling
* AI and ML ecosystem compatibility

---

## Rust

**Strengths**:

* Strong compile-time guarantees
* Excellent performance
* Enforces ownership and immutability patterns
* Ideal for deterministic engines

**Weaknesses**:

* Steeper learning curve
* More verbose iteration during early prototyping

**Best for**: Long-lived, correctness-critical engines

---

## JVM (Kotlin / Java / Scala)

**Strengths**:

* Mature tooling
* Strong ecosystem
* Good performance
* Functional paradigms available (especially Scala)

**Weaknesses**:

* GC pauses (usually manageable)
* Requires discipline to maintain immutability

**Best for**: Enterprise-grade engines, fast iteration with safety

---

## C++

**Strengths**:

* Maximum control and performance
* Familiar to many game developers

**Weaknesses**:

* Manual memory pitfalls
* Harder to enforce architectural discipline

**Best for**: Performance-critical engines with experienced teams

---

## Functional Languages (Haskell, OCaml, F#)

**Strengths**:

* Natural fit for immutable state machines
* Excellent correctness guarantees
* Elegant expression of rules

**Weaknesses**:

* Smaller talent pool
* Less mainstream tooling for games

**Best for**: Research-oriented or correctness-focused projects

---

## Python

**Strengths**:

* Extremely fast iteration
* Excellent AI/ML ecosystem

**Weaknesses**:

* Performance limitations
* Requires strong discipline to maintain invariants

**Best for**: Prototyping, AI experimentation, reference implementations

---

## Recommended Strategy

A common successful approach:

* Core engine in **Rust** or **JVM language**
* AI tooling in **Python**, consuming event logs
* UI and networking layered externally

---

# Minimal Recommended Module Layout

```
/engine
  /core
    GameState
    Action
    Event
    Invariants
  /rules
    ActionValidator
    EventDeriver
  /apply
    EventApplier
  /orchestrator
    GameEngine
    HistoryManager
  /query
    ReadModels
  /util
    RNG
    Identifiers

/adapters
  /ui
  /network
  /ai

/tests
  /unit
  /property
  /replay
```

## Module Responsibilities

* `core`: Pure domain types
* `rules`: Validation and rule logic
* `apply`: Deterministic state transitions
* `orchestrator`: Atomic execution and rollback
* `query`: Read-only projections
* `adapters`: Integration points
* `tests`: Verification and regression

---

## Final Note

If you keep this document as a living contract and refuse shortcuts that violate its principles, you will retain architectural clarity even as the game’s rules grow arbitrarily complex.
