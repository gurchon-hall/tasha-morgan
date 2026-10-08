# Open questions

Rules or card interactions that the official sources do not settle. Nothing listed here may be implemented by guessing. Format and procedure: see `.claude/skills/vtes-rules-reference/SKILL.md`.

## OQ-1: Prey/predator wording in a duel   (status: open)

- Situation: with two players, each Methuselah is the other's prey and predator (Rulebook §5). Some card texts distinguish prey from predator, or refer to "other Methuselahs" in a way written for 4–5 players.
- Sources read: Rulebook v1.1 §5; 2P variant page (modified 2025-05-20); 2P updates page (2026-10-03). No dedicated clarification found.
- Candidate readings: to be listed per card when encountered.
- Impacted cards: to be listed.

## OQ-2: Interface target   (status: resolved — digital first)

- Decision: digital-first. The engine owns the full game state and exposes explicit legal choices; the first implementation target is a CLI interface.
- Rationale: the project is built around deterministic state tracking, legal-action decision points, and engine-driven play, which are natural to a digital interface and easier to validate than a physical-table workflow.
- Scope: the physical-table workflow remains out of scope unless a concrete requirement appears. The project will proceed with digital play and CLI-first tooling by default.
