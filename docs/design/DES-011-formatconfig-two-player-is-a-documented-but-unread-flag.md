---
status: resolved
date: 2026-10-15
cards:
---

# DES-011 - `FormatConfig.two_player` is a documented but unread flag

- Context: `rules-auditor` found that `engine/format.py`'s own docstring
  claims "every 2P-only rule still reads this flag rather than being
  unconditional", but no code anywhere reads `two_player` -- every 2P
  delta (contested crypt cards staying in play, the 3-then-4 transfer
  ramp) is hardcoded unconditionally.
- Decision: accepted simplification, not a bug: CLAUDE.md §1 scopes
  4-5 player VTES out for now, and nothing ever constructs
  `FormatConfig(two_player=False)`, so the flag has no live branch to
  gate. `engine/format.py`'s docstring corrected to describe the
  current, unconditional reality instead of an unbuilt contract.
- Consequence: if 4-5 player support is ever added, every hardcoded
  2P-only call site above must be revisited to actually read
  `state.format.two_player` -- this decision does not pre-build that
  gate, only stops the docstring overclaiming it already exists.
