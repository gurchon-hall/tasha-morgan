---
status: resolved
date: 2026-10-14
cards: Voter Captivation; Scalpel Tongue
---

# RUL-010 - Voter Captivation/Scalpel Tongue - who may play it

- Situation: both cards are typed (at least partly) Action Modifier. Their
  earlier implementations (`cards/voter_captivation.py`,
  `cards/scalpel_tongue.py`'s basic/superior clauses) offered the play to
  *any* ready (Scalpel Tongue: ready and unlocked) vampire either
  Methuselah controls, independent of who is the political action's own
  acting/caller vampire. `rules-auditor` flagged this as a candidate rules
  violation, not a verified-safe implementer's choice: it contradicted this
  project's own Perfect Paragon precedent (ENG-021/RUL-009), where the
  structurally identical "[pre] This vampire gets +3 votes" immediately
  after a trigger clause was read as caller-only.
- Rules & interactions: Rulebook §2 Card Types (`data/sources/rulebook/
  2026-10-09/2-card-types.md:305-311`), verbatim: "The acting minion can
  play these cards... Some action modifier cards are played by minions
  'other than the acting minion'. Only minions controlled by the same
  Methuselah can play those cards." No on-file krcg ruling, nor a live
  VEKN card-rulings fetch, settles whether "this vampire" on either card
  means the acting vampire specifically, or any ready vampire of the
  controller.
- Solution (user ruling): Reading A -- "only usable by the acting vampire."
  Both cards now restrict any caller-side use strictly to the political
  action's own acting vampire, `context["caller_vampire_id"]`, per the
  quoted Rulebook default (absent an "other than the acting minion"
  override phrase on either card's text, the unqualified default applies).
  `voter_captivation.py` has no Reaction half to lean on, so this fully
  removes the non-caller Methuselah's own use of the card -- their copy of
  Voter Captivation is simply unplayable, an accepted consequence, not a
  gap. `scalpel_tongue.py` is asymmetric instead: its own Reaction half
  (`types == ["Action Modifier", "Reaction"]`) independently justifies the
  *non*-caller Methuselah's use (never "the acting minion" for this
  political action at all, so the Action-Modifier default does not reach
  them), kept exactly as it was -- any ready, unlocked qualifying vampire
  of theirs; only the caller-side half of its own eligibility changed, now
  requiring their own acting vampire specifically, with that vampire's own
  (necessarily already-locked, Rulebook §4) `locked` state correctly
  ignored for that check, unlike the non-caller Reaction-rule check.
  `cards/voter_captivation.py::_caller_vampire`,
  `cards/scalpel_tongue.py::_caller_may_play_basic`/`_caller_may_play_
  superior` implement this. Both cards stay `Status.IMPLEMENTED`.
