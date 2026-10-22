---
name: add-engine-hook
description: >-
  Workflow to give the engine a mechanism a card needs — a new `Hook`
  member, its dispatch site, tests, and closing the ENG entry that
  blocked the card. Use when a card is blocked on an `ENG` entry
  ("no <x> hook"), or when an engine gap is found while implementing
  or auditing a card.
---

# Adding an engine hook

Most `ENG` entries are "card X has no hook for Y". The engine owns the
timing and the decision points; the card only plugs into them
(CLAUDE.md §5).

## 1. Make sure a new hook is needed

- Read the `ENG` entry, the card snapshot (`data/cards/<id>.json`)
  and its rulings.
- Read `engine/hooks.py::Hook`: many members are generic siblings
  (`STEALTH_INCREASE` / `INTERCEPT_DECREASE`, `END_OF_ROUND` /
  `BEFORE_RANGE`). Extending or reusing one beats a card-specific
  hook. Name a new one after the game moment, never after the card.
- If the gap is how a rule reads, not a missing mechanism, it is a
  `RUL` entry instead (`vtes-rules-reference`).

## 2. Source the timing

Find the rulebook / 2P variant section that fixes *when* the effect
happens and *who* may act (acting side first, two-sided window,
mandatory). That section is the dispatch site's citation. No source →
`RUL` entry, stop.

## 3. Add the member and its dispatch site

- `Hook.<NAME>` in `engine/hooks.py`, no docstring.
- Its context in `engine/hook_contexts.py`: a `<Name>Context`
  `TypedDict` with exactly the keys the dispatch site passes (one per
  phase, joined in a union, if the keys differ by phase), added to
  `HOOK_CONTEXTS`. Its docstring, 3 lines max, is the hook's contract:
  dispatch style, who is asked, what `apply` or a provider returns,
  entry id. Every dispatch is checked against it: a missing or
  undeclared key raises `TypeError`.
- In the engine module that dispatches it: `<NAME>_HOOK = Hook.<NAME>`
  and the call. `tests/rules/test_hook_enum.py` fails if a wired
  member has no such constant, or a constant is not a member.
- Pick the dispatch helper by shape: `offer` / `offer_until_pass` /
  `resolve_impulse_window` for player choices (a `Decision` with the
  legal options), `sum_modifiers` / `union_modifiers` / `any_true` /
  `collect` for passive values, `run_effects` for mandatory reactions.
  A chosen option goes through `apply_chosen_option` (cost, then
  cancel-as-played, ENG-022/ENG-050).
- Not dispatched yet → add it to `UNWIRED_HOOKS` instead, with no
  context type; `Card.on` refuses it, `Card(also_uses=...)` can
  declare it. `tests/rules/test_hook_contexts.py` fails if a wired
  member has no context type.
- 2P-only behaviour is gated by the format config (CLAUDE.md §3).

## 4. Test the mechanism, not the card

Scenario tests under `tests/rules/` (`rules-scenario-test`) with a
test-only provider: `hooks.register(Hook.<NAME>, provider)` inside the
test; a test that dispatches directly passes the full context. The
autouse fixture in `tests/conftest.py` snapshots and restores the
catalogue; never call `hooks.clear()`. Cover each branch the source
names and assert what is offered, to whom, in which order.

## 5. Close out

- Rewrite the `ENG` entry as resolved: three bullets, `Solution`
  naming the hook and its dispatch site (`vtes-rules-reference`,
  "Closing an entry"). Regenerate the index.
- Report the card(s) now unblockable; unblocking them is
  `implement-card`'s job.
- `uv run python scripts/check.py`. Changes to combat, impulse or
  politics get a `rules-auditor` review.
