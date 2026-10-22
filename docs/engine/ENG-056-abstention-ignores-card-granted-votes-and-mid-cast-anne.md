---
status: open
date: 2026-10-23
cards: Scalpel Tongue; Queen Anne
---

# ENG-056 - Abstention ignores card-granted votes and mid-cast Anne

- Situation: a vote source is not tied to the vampire it belongs to, so
  an abstention cannot find a vampire's card-granted votes. Scalpel
  Tongue only targets `title:` casts, and Queen Anne only adds ids to
  `pending["forced_abstain"]` before casting.
- Sources read: RUL-016 (an abstention cancels all of the vampire's votes,
  card-granted included), RUL-018 (Queen Anne usable until polling
  closes, like Scalpel Tongue).
- Needed mechanism: `VoteSource` / `pending["extra_sources"]` entries
  record the vampire they belong to; a generic "vampire abstains" effect
  removes that vampire's remaining sources and cancels its casts (the
  ENG-027 retroactive cancellation, per vampire). Scalpel Tongue targets
  any vampire with a cast; Queen Anne is offered mid-cast too.
- Impacted code: `engine/politics.py` (`VoteSource`, `_cast_votes`,
  `_apply_retroactive_vote_cancellation`); `cards/scalpel_tongue.py`,
  `cards/queen_anne.py`, and the source-adding cards (Perfect Paragon,
  Modius, Alexa Draper, Oxford).
