---
status: open
date: 2026-10-23
cards: Carmelita Neillson
---

# RUL-019 - Carmelita Neillson - is a locked vampire "ready"

- Situation: Carmelita Neillson (201625): "Camarilla: While Carmelita is
  ready, you get +1 hand size." `cards/carmelita_neillson.py` gives the
  bonus only while she is in the ready region *and unlocked*, reading
  "ready" like a reaction card's "ready, unlocked minion". A locked
  Carmelita in the ready region gives no bonus today.
- Sources read: Rulebook §8 Glossary: "Ready minion: A minion in the ready
  region who can therefore perform actions and attempt to block actions";
  "Ready Region: Area containing a Methuselah's minions that are not in
  torpor." Rulebook §4 Gaining Votes: "A minion's votes and ballots can be
  used only when the minion is ready. Whether or not a minion is locked or
  unlocked does not have any impact on their ability to vote." No ruling
  on file for the card.
- Candidate readings: (a) ready = in the ready region, locked or not (the
  vote rule treats the two as independent); (b) ready = ready and
  unlocked (today's code, from "can therefore perform actions").
- Impacted code: `cards/carmelita_neillson.py`;
  `tests/cards/test_carmelita_neillson.py`.
