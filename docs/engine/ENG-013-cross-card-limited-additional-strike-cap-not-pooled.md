---
status: resolved
date: 2026-10-10
cards: Dust Up; Side Strike
---

# ENG-013 - Cross-card "(limited)" additional-strike cap not pooled

- Situation: Dust Up and Side Strike each tracked their own
  "(limited)" additional-strike cap privately per-card,
  per-vampire-instance — so nothing stopped one vampire from using
  *both* cards' grants in the same round (an illegal-play risk), and
  the cap never reset between rounds.
- Rules & interactions: §8 glossary, verbatim: "A minion cannot use
  more than one card or effect to gain additional strikes per round
  of combat."
- Solution: `run_combat` now creates a fresh, round-scoped
  `round_state` dict threaded into the dodge/additional-strike hook
  contexts; `additional_strike_limit_used`/
  `mark_additional_strike_limit_used` read/write a shared flag in it
  (degrading gracefully when offered outside `run_combat`). Both cards
  were migrated onto the shared helpers. A `rules-auditor` follow-up
  found and fixed a regression in the first landing: the flag was
  briefly a single flat boolean shared across *both* combatants,
  wrongly pooling the cap jointly instead of per-minion — fixed by
  keying it per `context["vampire"]`.
