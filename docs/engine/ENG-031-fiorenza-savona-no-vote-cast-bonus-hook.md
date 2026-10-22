---
status: resolved
date: 2026-10-14
cards: Fiorenza Savona
---

# ENG-031 - Fiorenza Savona - no vote-cast bonus hook

- Situation: Fiorenza Savona (krcg id 201616): "Camarilla: If you burn the
  Edge for a vote, you get +1 vote. If you burn a political action card for
  a vote, you get +1 vote." RUL-005's general referendum mechanism gives
  `_collect_vote_sources` a fixed set of `VoteSource`s with `votes` baked in
  before casting, and neither `POLLING_STEP_HOOK` phase nor
  `REFERENDUM_TALLIED_HOOK` can add a bonus to one *specific other* source's
  own vote count at the moment it is actually cast -- a missing engine
  primitive, not a ruling ambiguity.
- Rules & interactions: plain printed text; no ruling on file. User ruling
  2026-10-14 settled the one open scope question: "burning a political
  action card for a vote" is specifically the non-caller's
  `political_action_card_hand:{other_player}` burn-from-hand source (the
  only one actually burned for a vote), never the caller's own
  `political_action_card:{caller_player}` source (played/shown, not
  burned).
- Solution: added `VOTE_SOURCE_CAST_BONUS_HOOK` (`cards/registry.py::
  Hook.VOTE_SOURCE_CAST_BONUS`), dispatched by `engine/politics.py::
  _cast_votes` the instant a source is cast -- after its own cast-time side
  effects, before its votes are added to the tally *and* logged into
  `casts` (so an ENG-027 mid-cast cancellation of that same source
  retroactively subtracts the bonus back out too, no special case). Context:
  `caster`, `burns_edge`, `burns_pac_from_hand`, `direction`. Fiorenza
  Savona's own card module (`cards/fiorenza_savona.py`, `Status.
  IMPLEMENTED`) gates on either flag plus "caster controls an in-play
  (not uncontrolled/burned/removed) Fiorenza" -- no "while ready" qualifier
  is printed, so no zone/locked gate beyond that.
