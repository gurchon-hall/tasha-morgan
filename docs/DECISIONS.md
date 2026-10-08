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
