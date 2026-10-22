---
status: resolved
date: 2026-10-14
cards: Loup
---

# RUL-012 - Loup - controller-only or table-wide bonus

- Situation: `rules-auditor`, reviewing RUL-011's own landing, flagged that
  `cards/loup.py`'s own scope assumption ("Both clauses... bind to the
  *controller's own* Toreador vampires, never the opponent's") carried no
  citation — `_provide_loup`/`_provide_loup_burn` only ever read/burned the
  *acting* player's own `turn_cards`, so a Methuselah's Loup could never
  grant the bonus to, or be burned by, the *other* Methuselah's own
  Toreador vampire. Pre-existing since ENG-024's original pass; RUL-011 only
  made both offer points newly reach this same unexamined assumption.
- Rules & interactions: Loup's own printed text has no "you control" --
  plain "Toreador get +1 stealth... after a Toreador performs a successful
  action." No on-file krcg ruling addressed this scope question directly.
  Ruling via a trusted VEKN judge on the international rulings forum
  (pending official publication; posed scenario: a Loup in play, its
  controller's own vampires all failing to act, a second Methuselah's
  Masika with an Enkil Cog about to act): "Yes, [Masika] has +1 stealth[,]
  and Loup burns if [the action] succeeds (card text)." Confirms table-wide
  on both halves, matching the comparative template evidence found across
  the card pool (Week of Nightmares, Tremere Convocation: same unqualified
  "[clan] get +1 [stat]" shape, contrasted with vampire abilities that
  explicitly add "you control" whenever that narrower scope is meant).
- Solution: `cards/loup.py::_provide_loup`/`_provide_loup_burn` now check/
  burn every player's own `turn_cards`, not only the acting player's.
  `LOUP_STEALTH_GRANTED_KEY` became a per-*instance* cap (a `set[str]` of
  turn-card `instance_id`s, not a flat flag): two independently-played
  copies, one per Methuselah, are two separate sources and may both be
  activated for the same action. Only *playing* a copy from hand stays
  controller-bound, by construction (a Methuselah can only play from their
  own hand); that option is now offered alongside, not instead of, any
  already-in-play copy's own activation option, since RUL-012 means they are
  independent, additive opportunities.
