---
status: resolved
date: 2026-10-08
cards:
---

# DES-004 - "Predator cuts" modelled as an automatic RNG draw

- Context: 2P variant §3 Game Setup has the predator cut each
  shuffled deck before draws are taken, mirroring the physical-table
  anti-stacking ritual. The rulebook does not say *how* the digital
  engine should represent a "cut" of an already-random, engine-owned
  shuffle.
- Decision: `src/vtesbot/engine/rng.py::GameRNG.cut` performs the
  cut as a second, logged RNG draw (a random cut point), not as a
  `Decision` offered to the predator's agent.
- Rationale: a cut of an already-uniformly-shuffled deck is
  statistically inert -- cutting a uniform random permutation at any
  point yields another uniform random permutation, so a player's
  choice of cut point carries no information and cannot affect the
  outcome. The physical-table purpose of the cut (preventing deck
  stacking by the owner) is already fully guaranteed by the engine's
  trusted seeded shuffle. This is a judgment call about engine
  representation, not a sourced rule, and is recorded here per the
  project's no-guessing philosophy (CLAUDE.md §2) rather than left
  as a bare code comment.
- Consequence: the replay log still records the cut (as a random
  draw) so the step is not silently skipped, but no agent is ever
  asked to choose a cut point. If a future card or ruling ever makes
  the cut point strategically meaningful (e.g. a card that lets a
  player see/influence the cut), this decision must be revisited.
