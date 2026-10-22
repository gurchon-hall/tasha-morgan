---
status: resolved
date: 2026-10-22
cards: Dust Up; Celerity
---

# ENG-047 - Card discipline checks ignore disciplines granted by attachments

- Situation: card modules gated their discipline requirements on the
  vampire's printed disciplines (`vampire.card.disciplines`), so a level
  granted by an attachment did not count: an Anarch with Celerity attached
  and no printed [cel] was refused Dust Up [cel], and a second Celerity
  copy never unlocked [CEL] effects. Found by `rules-auditor` reviewing the
  card authoring API; ENG-002 had built `effective_disciplines` but left the
  card-side readers for a later pass.
- Rules & interactions: Rulebook §2 Card Types: "The vampire's Disciplines
  determine which library cards they can play"; a Discipline card gives
  "the basic level of a new Discipline or increasing the level of a
  Discipline from basic to superior". Disciplines from attachments count
  like printed ones.
- Solution: every card gate reads `engine/attachments.py::
  effective_disciplines(state, vampire)` (25 modules), and
  `cards/common.py::discipline_level` / `has_discipline` take `state` and
  use it. Celerity's own `DISCIPLINE_LEVEL_MODIFIER` provider still reads
  printed levels, since it is one of the sources `effective_disciplines`
  folds in. Covered by `tests/cards/test_common.py`. Changing the game path
  made Brujah-mirror seed 12 a random-agent stall (winnable, undecided at
  the turn cap), listed in `tests/sim/test_bot_vs_bot.py::
  KNOWN_RANDOM_AGENT_STALLS`.
