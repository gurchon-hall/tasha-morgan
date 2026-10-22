---
status: resolved
date: 2026-10-08
cards:
---

# DES-003 - Digital-first interface

- Context: the project architecture centers on a deterministic
  rules engine, explicit decision points, and full game-state
  tracking. This is a strong fit for a digital interface where the
  engine owns the complete state.
- Decision: the default interface target is digital-first, with the
  initial implementation built as a CLI that drives the engine
  directly.
- Consequence: the project will optimize for engine-owned state and
  legal action enumeration rather than a physical-table workflow;
  the latter remains out of scope unless a concrete requirement
  emerges.
