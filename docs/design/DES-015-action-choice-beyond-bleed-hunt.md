---
status: resolved
date: 2026-10-17
cards:
---

# DES-015 - `action_choice` beyond bleed/hunt

- Context: an external review of the DES-013/DES-014 delivery found that the new
  `recruit_count`/`pool_spent_recruit` economic counters (`sim/invariants.py`)
  read exactly `0.0` across every benchmark. Root cause: `_action`
  (`agents/heuristic.py`) only ever looked up `"bleed"` and `"hunt"` from
  `decision.choices` and picked between those two, falling through to
  `bleed or hunt` for any other legal `action_choice` option --
  `diablerise`, a card-granted recruit (`RECRUIT_ALLY_PLAY_HOOK`, e.g. 47th
  Street Royals, krcg 102217, in the Brujah suggested deck), an action-card
  play (`ACTION_CARD_PLAY_HOOK`, e.g. Kine Resources Contested, Line Brawl,
  Fleetness, Enchant Kindred), or an attachment-removal action
  (`ATTACHMENT_REMOVAL_ACTION_HOOK`) -- all merged into the same
  `action_choice` decision alongside bleed/hunt by `engine/phases/
  minion.py::_choose_and_perform_action`. Not a card or engine bug: the
  engine correctly offers the option; the heuristic was structurally blind
  to anything that wasn't literally `"bleed"` or `"hunt"`, so such an
  option could never be chosen regardless of how good it legally was.
- Decision: `_action`/`_score_action` now score every choice actually
  present in `decision.choices`, not just two hardcoded values. Two new
  flat constants: `OTHER_ACTION_LOSES_TO_BLEED_SCORE = 0.5` and
  `OTHER_ACTION_BEATS_HUNT_SCORE = 1.5` score any choice that is neither
  `"bleed"` nor `"hunt"` -- beating hunting (hunting is itself just a
  no-damage fallback for a dry vampire) whenever the vampire's blood is at
  or below `LOW_BLOOD` (where hunting would otherwise be scored `1.0`), but
  losing to an ordinary bleed above that threshold (scored `1.0`); the
  existing lethal-bleed `inf` override (DES-014) still wins over everything.
  This is deliberately card-blind, matching DES-013's P3 deferral: the agent
  has no generic way to tell a strong "other" option from a weak one, so
  all of them get the same flat treatment -- "worth taking only when the
  alternative was going to be hunting anyway," not a claim that recruiting,
  diablerising, or any specific action-card play is actually good here.
- Consequence: `recruit_count`/`pool_spent_recruit`, and any future
  card-granted `action_choice` option, are no longer structurally
  unreachable -- confirmed non-zero below, in the (narrow) states where
  this scoring prefers them over hunting. `diablerise` and action-card
  options (`kine_resources_contested:play`, `line_brawl:*`, `fleetness:*`,
  `enchant_kindred:*`, ...) are scored by the same generic rule, not
  because any of their specific effects were evaluated.
- Before/after benchmark (seeds 0-199, `python -m vtesbot.sim.benchmark
  200 versus`/`... 200 selfplay`, same seed range and deck as DES-013/DES-014):

  | metric | before | after |
  | --- | --- | --- |
  | versus win rate (95% Wilson) | 1.000 (0.981-1.000) | 1.000 (0.981-1.000) |
  | versus mean turns | 21.2 | 21.2 |
  | selfplay win rate (95% Wilson) | 0.560 (0.491-0.627) | 0.545 (0.476-0.613) |
  | selfplay first-seat win rate | 0.470 | 0.465 |
  | selfplay mean turns | 16.5 | 16.7 |
  | selfplay recruit_count total [P1/P2] (200 games) | 0/0 (impossible) | 3/0 |

  `before`'s `recruit_count` is exactly `0` by construction (no code path
  before this change could ever return a recruit choice), not a rounding
  artifact; `after`'s `3/0` is the exact sum (the `.1f`-rounded per-game
  mean the benchmark CLI prints reads `0.0` either way at this rarity,
  which is itself a benchmark-reporting precision note, not a sign the fix
  did nothing -- verified by summing `MatchResult.economic_counts`
  directly instead of trusting the rounded CLI output). Every other metric
  stays within (`versus`) or close to and overlapping (`selfplay`) the
  before interval, with no stuck game introduced -- kept per this reading.
- Addendum (2026-10-17), attempted and reverted: a flat
  `OTHER_ACTION_BASE_SCORE = 2.0`, strictly above `_score_action`'s own
  `1.0` ceiling so a non-bleed/non-hunt option always wins whenever legal
  (short of a lethal bleed), was tried first, reasoning that the engine
  already gates these options on their own legality/affordability.
  Benchmarked (seeds 0-199, same commands): selfplay win rate dropped
  0.560 to 0.455, stuck (max-turns) games went from 0/200 to 15/200, mean
  selfplay turns rose 16.5 to 52.8, `bleed_pool_dealt` collapsed 9.1 to 1.7
  per game, and `lethal_bleed_count` dropped 0.6 to 0.4; `versus`'s Wilson
  lower bound also slipped 0.981 to 0.972 with one stuck game appearing.
  Root cause: once any action-card option is in hand it stays legally
  offered every turn, so an unconditional preference for "other" over
  bleed/hunt repeatedly burns the minion action on a card play instead of
  bleeding, collapsing aggression on both sides at once -- a clear
  regression by DES-014's own keep/revert rule. Reverted in favor of the
  two-tier version above, which never outranks an ordinary bleed.
- Addendum (2026-10-17), lost self-play games audited, nothing else acted
  on: sampled a batch of 200 self-play games (`sim.runner.run_many` with
  `report_sample_losses_and_ties=True`) and read several losing games'
  decision logs (`sim/report.py::format_decision_log`). One recurring
  pattern: in some losses, one side's `minion_phase_choice` offers only a
  single `act_with:` vampire for many turns in a row while the other side
  accumulates two or three, because `_score_bring_crypt`'s existing
  `has_uncontrolled` gate (DES-014) keeps directing every transfer into
  whichever single uncontrolled vampire already exists until it reaches
  capacity rather than ever starting a second one in parallel -- this is
  the exact trade-off DES-014's own "tried and reverted" `bring_crypt`
  addendum already investigated and found to regress the benchmark; not
  re-attempted here, left as a P2/lookahead-grade question (DES-013) about
  when starting a second vampire in parallel is worth it. No other
  generic, card-blind, cheaply-benchmarkable weakness was found in this
  sample: `block_attempt`, `strike_choice`, `mend_damage`, `press`,
  `maneuver_choice`, `additional_strike_choice`, `edge_pool_gain`,
  `contest_resolution`/`master_card_contest_resolution`,
  `wider_view_remove_target`, and `end_of_round` all still fall back to
  random play, exactly as DES-008/DES-014 already document -- reconfirmed, not a
  new finding, and out of this entry's scope.
