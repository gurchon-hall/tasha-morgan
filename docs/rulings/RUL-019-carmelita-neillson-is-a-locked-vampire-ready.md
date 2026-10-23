---
status: resolved
date: 2026-10-23
cards: Carmelita Neillson
---

# RUL-019 - Carmelita Neillson - is a locked vampire "ready"

- Situation: Carmelita Neillson (201625): "Camarilla: While Carmelita is
  ready, you get +1 hand size." `cards/carmelita_neillson.py` gave the
  bonus only while she was in the ready region *and unlocked*, so a locked
  Carmelita gave nothing.
- Rules & interactions: Rulebook §8 Glossary: "Ready Region: Area
  containing a Methuselah's minions that are not in torpor." Rulebook §4
  Gaining Votes: "A minion's votes and ballots can be used only when the
  minion is ready. Whether or not a minion is locked or unlocked does not
  have any impact on their ability to vote." No ruling on file for the
  card.
- Solution (user ruling, 2026-10-23): Carmelita works while ready, locked
  or unlocked; only torpor and leaving play end the bonus. The module
  checks `zone == "ready"` alone. Covered by
  `tests/cards/test_carmelita_neillson.py`.
