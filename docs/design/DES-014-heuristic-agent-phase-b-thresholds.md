---
status: resolved
date: 2026-10-17
cards:
---

# DES-014 - Heuristic agent Phase B thresholds

- Context: DES-013's Phase B -- the generic, non-card slice of the audit
  report's P1 -- on `agents/heuristic.py`. All thresholds below are
  untested assumptions (DES-008's own framing), not community strategy
  content, kept or discarded only by the before/after benchmark numbers
  at the end of this entry, not by inspection.
- Decision:
  1. `action_choice` gets a `BLEED_AMOUNT_FLOOR = 1` lethal-bleed override:
     if the opponent's pool is at or below this floor, bleed scores
     `+inf` and is always chosen, overriding the existing `LOW_BLOOD`
     blood check. The floor is the engine's own unmodified base bleed
     amount (`engine/phases/minion.py`'s `BLEED_AMOUNT`), a conservative
     lower bound: card-sourced bleed bonuses aren't visible generically
     to the agent, so this floor can only undercount a bleed's true
     lethality, never overcount it -- it will not fire a "lethal" bleed
     that then under-delivers.
  2. `influence_action`'s `add_blood`/`bring_crypt`/`remove_blood`
     targeting moves from if/elif branching to `_score_add_blood`/
     `_score_bring_crypt`/`_score_remove_blood` + `max(choices, key=...)`.
     `_score_add_blood` keeps the existing "vampire nearest capacity"
     ranking as the dominant term among `add_blood` targets (unchanged
     from before), adds a flat `ADD_BLOOD_BASE_SCORE` so a normal
     `add_blood` still beats `end_phase` (matching the pre-Phase-B
     unconditional preference), and turns the old hard
     `pool > CRITICAL_POOL` gate into a graded penalty: an `add_blood`
     that would itself drop pool to or under `CRITICAL_POOL` is
     penalized hard enough to lose to `end_phase`, instead of the whole
     branch being blocked whenever pool already happened to be low.
     `_score_bring_crypt` keeps its existing trigger (only scored when no
     uncontrolled vampire exists) but is now scored as
     `pool_after_cost - CRITICAL_POOL` (a flat 1-pool cost -- this engine
     has no variable per-crypt-card cost, confirmed against
     `engine/phases/influence.py::_apply`) instead of winning
     unconditionally whenever legal, so it can lose to `end_phase` when
     pool is low even while triggered. `_score_remove_blood` keeps
     `CRITICAL_POOL` as a hard entry gate (true emergency behavior, not
     softened) and the existing "fullest uncontrolled vampire" ranking.
     `reveal` stays an unconditional first-preference short-circuit.
  3. `master_phase_action` is left unchanged: `decision.choices` is
     already legality-filtered by the engine's hook providers, and
     `Observation` carries no effect-preview field, so "skip a useless
     play" isn't cheaply derivable without card-specific knowledge --
     deferred to milestone 6/7 (audit report P3), not an oversight.
- Before/after benchmark (seeds 0-199, `python -m vtesbot.sim.benchmark
  200 versus`/`... 200 selfplay`, same seed range as DES-013's Phase A
  baseline):

  | metric | before | after |
  | --- | --- | --- |
  | versus win rate (95% Wilson) | 1.000 (0.981-1.000) | 1.000 (0.981-1.000) |
  | versus mean turns | 21.2 | 21.2 |
  | selfplay win rate (95% Wilson) | 0.510 (0.441-0.578) | 0.560 (0.491-0.627) |
  | selfplay first-seat win rate | 0.500 | 0.470 |
  | selfplay mean turns | 15.1 | 16.5 |

  The versus Wilson lower bound is unchanged at an already-near-ceiling
  0.981 (the random opponent is a weak ceiling-test, so "no regression"
  counts as a pass here, per the plan's own framing); the selfplay win
  rate moved from 0.510 to 0.560, still well inside a 95% Wilson band
  that brackets 0.5 both before and after, and the first-seat win rate
  stayed close to 0.500 -- no sign of a hidden first-mover artifact or a
  scoring bug. Kept per this reading.
- Consequence: `action_choice`/`influence_action` now route through
  explicit `_score_*` functions instead of if/elif branching, making the
  next revision (e.g. recalibrating a constant, or a future P2 lookahead
  reusing these as a leaf evaluation) a matter of editing one function,
  not re-deriving the branch order. Not handled yet (random, unchanged
  from DES-008): blocks, combat steps, damage mending, votes, contest
  resolution, edge gain, card-specific targets; `master_phase_action`'s
  "play first offered card" and `minion_phase_choice`'s "highest blood
  vampire first" are also unchanged by this entry.
- Addendum (2026-10-17), considered and deferred: `discard_phase_action`
  always passes (DES-008 item 4), forfeiting a once-per-turn discard+redraw
  (`engine/phases/discard.py`). `action_choice` can legally offer more
  than bleed/hunt via `ACTION_CARD_PLAY_HOOK`/`RECRUIT_ALLY_PLAY_HOOK`
  (`engine/phases/minion.py::_choose_and_perform_action`), and the Brujah
  suggested deck does carry such cards (Enchant Kindred, Fleetness, Kine
  Resources Contested, Line Brawl, 47th Street Royals) -- but deciding
  *which* hand card is currently dead enough to discard needs per-card
  effect knowledge the agent doesn't generically have, the same gap that
  left `master_phase_action` unchanged above. A card-blind policy (e.g.
  "always discard the first hand card") isn't a reasoned decision, just a
  different gamble -- not attempted, given the bring_crypt addendum right
  above already shows a plausible-looking blind change regressing the
  benchmark. Deferred to milestone 6/7 alongside the rest of DES-013's P3.
- Addendum (2026-10-17), attempted and reverted: `engine/phases/
  influence.py:69-99` offers `bring_crypt` whenever transfers/pool/
  crypt-deck allow, with no check on whether an uncontrolled vampire
  already exists -- so the engine can legally offer `bring_crypt` and
  `add_blood` in the very same decision, which `_score_bring_crypt`'s
  `has_uncontrolled` gate (above) never actually lets compete; it always
  loses to any `add_blood` target once one exists, regardless of how far
  from capacity it is. Tried: dropping the gate and scoring `bring_crypt`
  on the same capacity-distance scale as `_score_add_blood`, assuming a
  placeholder "4 blood still needed" for the unseen next crypt card (the
  agent can't see its real capacity before bringing it in). Benchmarked
  (seeds 0-199, same commands as above) against the DES-014 baseline:
  versus Wilson lower bound dropped 0.981 to 0.964 (2/200 losses to
  random, versus 0 before) and selfplay first-seat win rate spiked to
  0.975 (versus ~0.50) with mean game length up roughly 50% in both
  benchmarks -- a clear regression and a first-mover-artifact bug
  signal, not an improvement, by this entry's own keep/revert rule.
  Reverted; `_score_bring_crypt`'s gate stays exactly as decided above.
  Root cause not fully diagnosed (plausibly: competing for `add_blood`
  against a barely-started recruit lets the agent spread transfers across
  multiple half-filled uncontrolled vampires instead of finishing any one
  of them) -- left as a documented dead end rather than investigated
  further, since the simpler gated version already passes its own bar and
  P2/lookahead-grade reasoning about "worth starting a second recruit in
  parallel" is exactly the kind of thing DES-013 defers to milestone 7.
