---
status: resolved
date: 2026-10-23
cards: Scalpel Tongue; Queen Anne; Perfect Paragon
---

# RUL-016 - Abstaining cancels every vote of the vampire

- Situation: Scalpel Tongue makes a vampire abstain, "this cancels the
  chosen vampire's votes and ballots", but `cards/scalpel_tongue.py` only
  targets and cancels `title:` casts. Votes a card gives that vampire
  (Perfect Paragon's "This vampire gets +3 votes", Modius, Alexa Draper)
  stay counted, and a caller without a title who cast such votes cannot be
  chosen. Found by `rules-auditor` reviewing ENG-051.
- Rules & interactions: Scalpel Tongue (101686): "Choose a vampire who has
  cast votes or ballots in this referendum. The chosen vampire is locked
  and abstains (this cancels the chosen vampire's votes and ballots)."
  Rulebook §4 Gaining Votes: "all of the votes and ballots from any given
  vampire or other source must be cast in agreement as a group."
- Solution (user ruling, 2026-10-23): abstaining cancels all votes and
  ballots of that vampire as a single source, title and card-granted votes
  alike; any vampire that cast such votes can be chosen. Implementation:
  ENG-056.
