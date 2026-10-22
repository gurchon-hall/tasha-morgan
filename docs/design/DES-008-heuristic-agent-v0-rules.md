---
status: resolved
date: 2026-10-14
cards:
---

# DES-008 - Heuristic agent v0 rules

- Context: milestone 5. A random-legal log showed ~2 reveals/game,
  add_blood 82 vs remove_blood 40 per game (blood shuffled back and
  forth), early end of influence, and few minion-phase actions.
- Decision: `agents/heuristic.py` applies the rules below by
  `decision.kind`; every other kind falls back to a seeded random
  choice. All thresholds are untested assumptions, not community
  strategy content.
  1. `influence_action`: reveal if offered; with pool above 2, bring a
     crypt card when no uncontrolled vampire exists, else add blood to
     the uncontrolled vampire nearest capacity; with pool at most 2,
     remove blood from the fullest uncontrolled vampire (2 transfers)
     if offered; otherwise `end_phase`.
  2. `minion_phase_choice`: act with the ready vampire holding the
     most blood before ending the phase.
  3. `action_choice`: hunt when the acting vampire has at most 1
     blood, otherwise bleed (in 2P the opponent is both prey and
     predator). Card-granted action options are never chosen.
  4. `master_phase_action`: play the first offered card (no card
     evaluation, so "harmless" is not established); `discard_phase_action`:
     pass; `hand_size_discard`: first offered card.
- Not handled yet (random): blocks, combat steps, damage mending,
  votes, contest resolution, edge gain, card-specific targets.
