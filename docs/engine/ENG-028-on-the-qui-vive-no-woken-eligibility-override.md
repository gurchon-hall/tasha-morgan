---
status: resolved
date: 2026-10-14
cards: On the Qui Vive
---

# ENG-028 - On the Qui Vive - no "woken" eligibility override

- Situation: On the Qui Vive (krcg id 101321, Reaction): "Only usable by a
  locked minion... This minion wakes (they ignore the requirement to be
  unlocked for playing reaction cards and attempting to block until the end
  of the action). If this minion is an ally, they do not unlock as normal
  during their next unlock phase." Unlike Organized Resistance/Second
  Tradition: Domain's "burn to unlock and force a block" shape
  (`BLOCK_CANDIDATE_INJECTION_HOOK`, ENG-018), this card forces nothing and
  grants no intercept — it only restores the playing minion's own ordinary
  *eligibility* to be offered as a normal block candidate (still subject to
  the usual stealth/intercept ping-pong) and to play further reaction
  cards, for the rest of the current action, while remaining structurally
  `locked`. Neither `engine/action.py::attempt_block` (candidates hardcoded
  to `state.ready_unlocked_vampires`) nor any existing reaction-card
  provider's own hardcoded `vampire.is_ready_unlocked` check had a hook for
  this override; allies additionally had no unconditional unlock step at
  all (`engine/phases/unlock.py::_unlock_own_allies`), making the card's own
  ally footnote incoherent to build on top of.
- Rules & interactions: plain card text; no ruling settles the engine shape
  (the two candidate readings were engine-internal design choices, not
  ruling questions).
- Solution (Reading A, the more generalizable of the two candidates):
  `VampireInPlay.woken` (`engine/state.py`), a transient per-vampire flag —
  `is_ready_unlocked` now also returns `True` while `woken` is set, even if
  `locked`, so `ready_unlocked_vampires`/`attempt_block` and every existing
  reaction-card provider's own `is_ready_unlocked` check pick it up with no
  per-card change. `engine/action.py::clear_woken_vampires`, called from
  both of `perform_minion_action`'s own exit points (unblocked-resolved;
  blocked-then-combat-resolved — the only two ways an action can end,
  since every minion action runs through that function), sweeps the flag
  back off for both players at the end of the action. `_unlock_own_allies`
  (`engine/phases/unlock.py`) gained the unconditional "unlock all ready
  allies" step it was missing entirely (a real, if previously dormant, gap
  — ally bleed/block/combat participation stays out of engine scope, so
  nothing read a ready ally's own `locked` state before now), plus
  `AllyInPlay.skip_next_unlock`, the one-shot override the card's own ally
  footnote needs. On the Qui Vive's own card module is not written; both
  primitives are complete.
