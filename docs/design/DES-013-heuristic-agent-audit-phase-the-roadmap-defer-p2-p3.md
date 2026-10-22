---
status: resolved
date: 2026-10-17
cards:
---

# DES-013 - Heuristic agent audit -- phase the roadmap, defer P2/P3

- Context: an external audit report proposed a four-tier roadmap for
  `agents/heuristic.py` -- P0 (benchmark/instrumentation reliability), P1
  (contextual heuristics: bleed/hunt, recruitment, blood/pool allocation),
  P2 (a `score(state, action)` evaluation function + limited lookahead),
  P3 (card-specific evaluators + calibration on a held-out seed set). The
  report was checked against the actual code, not taken at face value: its
  "always bleed" claim doesn't hold (`_action` already branches on
  `LOW_BLOOD`, pinned by
  `tests/agents/test_heuristic.py::test_bleeds_with_blood_and_hunts_when_low`),
  but the absence of any scoring abstraction and of economic detail in
  `sim/report.py`'s `batch_results.csv` is accurate.
- Decision: implement only the report's P0 (benchmark instrumentation --
  economic counters, a heuristic-vs-heuristic self-play baseline, a
  position-swap check, wider decision-log sampling) and the generic,
  non-card slice of P1 (a lethal-bleed floor on `action_choice`, pool-aware
  scoring for `bring_crypt`/`add_blood`/`remove_blood`) now, as milestone 5
  work. P2 (lookahead/minimax) and P3 (card-specific evaluators, ML-style
  calibration) are explicitly deferred, not built:
  1. P2 needs a capability CLAUDE.md §8 already flags as an open,
     deliberately unsettled architecture decision (heuristics vs
     determinized MCTS/ISMCTS vs RL, reserved for milestone 7). Building a
     lookahead now means making that call ad hoc inside `agents/`, most
     likely requiring an engine-level state-clone/determinization
     primitive that blurs the "pure core" boundary (CLAUDE.md §5) and
     would itself need `rules-auditor` review as a core-engine change.
  2. P3 needs a card pool milestone 6 ("full 2P allowed list") hasn't
     finished building yet -- card-specific evaluators written against a
     partial registry would need rewriting as more cards land, and the
     report's own calibration method (train/validate on separate seed
     sets, check generalization to unseen configurations) has nothing
     stable to generalize against until milestone 6 is done.
- Consequence: a future revisit of P2 belongs with milestone 7 (with its
  own `score`/lookahead decision entry then); a future revisit of P3
  belongs after milestone 6. Phase A/B's own concrete thresholds
  (lethal-bleed floor, pool-aware recruit scoring) get their own decision
  entry once implemented, following DES-008's framing (design choices, not
  VtES facts).
