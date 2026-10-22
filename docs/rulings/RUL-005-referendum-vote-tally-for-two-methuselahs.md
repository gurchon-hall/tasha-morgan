---
status: resolved
date: 2026-10-09
cards:
---

# RUL-005 - Referendum vote tally for two Methuselahs

- Situation: the condensed rules mapping gave vote sources and "terms
  chosen only after success" but not what votes are compared against,
  what "ties fail" means, or whether "automatically passing"
  ([PIB 20150105]/[LSJ 19980107], printed on Perfect Paragon/Scalpel
  Tongue) is a duel-specific mechanic.
- Rules & interactions: rulebook, fetched live: casting happens "in any
  order," tallied for/against, ties fail — this degrades cleanly to
  2P (an uncontested referendum is 0-for/0-against, which ties, same
  as any player count); the 2P variant has no referendum-procedure
  override beyond the already-known title-contest exception;
  "automatically passing" (General Ruling [PIB 20150105]) is a
  card-text-triggered category (a card whose own text declares its
  called referendum passes automatically), unrelated to player count —
  none of this pool's three Political Action cards carry that text.
- Solution: `political_action` calls `resolve_referendum`
  (`engine/politics.py`), which runs a pre-cast `"polling_step"` hook
  window, collects every vote source (the caller's own card vote —
  offered as a real decision, not hardcoded — titled ready vampires
  via `TITLE_VOTES`, an Edge-burn source, any hook-added source, and a
  non-calling Methuselah's own 1-vote burn-from-hand of a different
  political action card), lets each cast for/against/abstain in
  table-order rotation (RUL-006), dispatches a post-tally
  `REFERENDUM_TALLIED_HOOK`, and tallies (ties/0-0 fail).
  `REFERENDUM_RESOLVED` is reserved for a later, fully-post-resolution
  trigger (Voter Captivation), not yet dispatched. Hook contexts carry
  only `caller_vampire_id`, never the live object (information
  hiding). Disputed Territory, Kine Resources Contested, Parity Shift,
  Alexa Draper, Diana Iadanza's "+1 bleed" clause, and Marcos Belegrad
  now have everything the engine needs but remain `blocked` pending a
  `card-implementer` pass; Perfect Paragon/Queen Anne need further
  card-specific work; Voter Captivation needs `REFERENDUM_RESOLVED`'s
  own dispatch call site built first. User ruling: declining the
  caller's own clause-1 vote does not unlock the clause-2
  burn-from-hand option for the caller — the calling card consumes
  that vote slot the instant it calls the referendum, regardless of
  whether the automatic vote is later cast or declined.
