---
status: resolved
date: 2026-10-13
cards: Diana Iadanza
---

# ENG-023 - Diana Iadanza - no cancel-type marker

- Situation: ENG-022 (resolved) built `engine/hooks.py::apply_chosen_option`
  but left `cancel_context` carrying no structured marker of the canceled
  option's own card type -- Diana's clause 1 ("Diana can burn 1 blood to
  cancel a *reaction card* as it is played") needs exactly that marker, to
  tell a genuine Reaction-card play apart from the same referendum-phase
  window's other, non-Reaction providers (Modius's discard-a-master-card
  ability, Oxford University, England's polling-step burn).
- Rules & interactions: a missing engine primitive, not a ruling question.
  The 5 on-file rulings for the generic "cancel as played" mechanic say
  nothing about a referendum-level cap on Diana's own ability; that cap
  comes separately from Rulebook §3 "Wording templates" > "During X, do
  Y": "only one Y can be done per X with this card."
- Solution: `HookOption` gained `played_card_type` (`engine/hooks.py`),
  set by every card-playing provider to its printed card type and left at
  `None` for a printed-ability activation; `apply_chosen_option` threads it
  into `CANCEL_AS_PLAYED_HOOK`'s context as `canceled_card_type`. Diana
  Iadanza (`src/vtesbot/cards/diana_iadanza.py`) then implemented clause 1
  against it, gated to Reaction-type options, to a referendum Diana herself
  called, and capped once per referendum via `pending["diana_iadanza_
  canceled"]`. `Status.IMPLEMENTED`.
