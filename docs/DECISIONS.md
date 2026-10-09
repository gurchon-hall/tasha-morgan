# Decisions

Architecture and design decisions. Strategy heuristics of the bot are recorded here as design choices, not as VtES facts.

## D-1: Target format = VEKN two-player variant (2026-10-08)

- Context: VtES is designed for 4–5 players; VEKN runs an open two-player playtest with a closed list of allowed cards.
- Decision: the bot targets only the 2P variant and only the allowed list, versioned by VEKN update date.
- Consequence: card implementation scope is bounded; the format data must be re-synced when VEKN publishes updates.

## D-2: Legality by construction (2026-10-08)

- The engine enumerates legal choices at every decision point; agents can only pick from them.

## D-3: Digital-first interface (2026-10-08)

- Context: the project architecture centers on a deterministic rules engine, explicit decision points, and full game-state tracking. This is a strong fit for a digital interface where the engine owns the complete state.
- Decision: the default interface target is digital-first, with the initial implementation built as a CLI that drives the engine directly.
- Consequence: the project will optimize for engine-owned state and legal action enumeration rather than a physical-table workflow; the latter remains out of scope unless a concrete requirement emerges.

## D-4: "Predator cuts" (2P variant SS3 setup) modelled as an automatic RNG draw, not a player `Decision` (2026-10-08)

- Context: 2P variant SS3 Game Setup has the predator cut each shuffled deck before draws are taken, mirroring the physical-table anti-stacking ritual. The rulebook does not say *how* the digital engine should represent a "cut" of an already-random, engine-owned shuffle.
- Decision: `src/vtesbot/engine/rng.py::GameRNG.cut` performs the cut as a second, logged RNG draw (a random cut point), not as a `Decision` offered to the predator's agent.
- Rationale: a cut of an already-uniformly-shuffled deck is statistically inert -- cutting a uniform random permutation at any point yields another uniform random permutation, so a player's choice of cut point carries no information and cannot affect the outcome. The physical-table purpose of the cut (preventing deck stacking by the owner) is already fully guaranteed by the engine's trusted seeded shuffle. This is a judgment call about engine representation, not a sourced rule, and is recorded here per the project's no-guessing philosophy (CLAUDE.md SS2) rather than left as a bare code comment.
- Consequence: the replay log still records the cut (as a random draw) so the step is not silently skipped, but no agent is ever asked to choose a cut point. If a future card or ruling ever makes the cut point strategically meaningful (e.g. a card that lets a player see/influence the cut), this decision must be revisited.

## D-5: Card-hook and card-registry catalogues are a static, module-level table, not `GameState` (2026-10-09)

- Context: CLAUDE.md SS5 says "no global state ... in `engine/`"; `src/vtesbot/engine/hooks.py` (which hook points exist and which card modules answer them) and `src/vtesbot/cards/registry.py` (which cards are implemented/blocked) are both module-level dicts populated once, at import time, by every `src/vtesbot/cards/*.py` module's top-level `register(...)` call.
- Decision: these two catalogues are deliberately *not* fields on `GameState`. "No global state" targets the mutable, seeded, per-game state (`GameState`, `GameRNG`) that must be deterministic and replayable turn-by-turn; a catalogue of which rules the engine's `cards/` package knows how to apply is static program configuration, identical in kind to `src/vtesbot/cards/registry.py`'s own card catalogue (explicitly asked for by CLAUDE.md SS6: "registry entry"), and does not vary within or between games built from the same installed code.
- Consequence: `engine/hooks.py` functions (`offer`, `sum_modifiers`, `offer_until_pass`, `resolve_impulse_window`) take the live `GameState` as a parameter and only ever *read* game state through it (to decide whether a registered provider's option currently applies) -- no hook function stores or mutates anything outside the `GameState` it is given. Tests that register temporary fake providers must remove them afterwards (`hooks.unregister`/`hooks.clear`) so the catalogue does not leak between tests, since it is shared process-wide state.
