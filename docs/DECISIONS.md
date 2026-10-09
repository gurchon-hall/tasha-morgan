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
