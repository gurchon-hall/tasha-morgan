---
status: resolved
date: 2026-10-09
cards:
---

# DES-005 - Card-hook/registry catalogues are static, not `GameState`

- Context: CLAUDE.md §5 says "no global state ... in `engine/`";
  `src/vtesbot/engine/hooks.py` (which hook points exist and which
  card modules answer them) and `src/vtesbot/cards/registry.py`
  (which cards are implemented/blocked) are both module-level dicts
  populated once, at import time, by every
  `src/vtesbot/cards/*.py` module's top-level `register(...)` call.
- Decision: these two catalogues are deliberately *not* fields on
  `GameState`. "No global state" targets the mutable, seeded,
  per-game state (`GameState`, `GameRNG`) that must be deterministic
  and replayable turn-by-turn; a catalogue of which rules the
  engine's `cards/` package knows how to apply is static program
  configuration, identical in kind to
  `src/vtesbot/cards/registry.py`'s own card catalogue (explicitly
  asked for by CLAUDE.md §6: "registry entry"), and does not vary
  within or between games built from the same installed code.
- Consequence: `engine/hooks.py` functions (`offer`, `sum_modifiers`,
  `offer_until_pass`, `resolve_impulse_window`) take the live
  `GameState` as a parameter and only ever *read* game state through
  it (to decide whether a registered provider's option currently
  applies) -- no hook function stores or mutates anything outside
  the `GameState` it is given. Tests that register temporary fake
  providers must remove them afterwards (`hooks.unregister`/
  `hooks.clear`) so the catalogue does not leak between tests, since
  it is shared process-wide state.
