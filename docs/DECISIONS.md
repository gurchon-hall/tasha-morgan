# Decisions

Architecture and design decisions. Strategy heuristics of the bot
are recorded here as design choices, not as VtES facts.

## D-1: Target format = VEKN two-player variant (2026-10-08)

- Context: VtES is designed for 4–5 players; VEKN runs an open
  two-player playtest with a closed list of allowed cards.
- Decision: the bot targets only the 2P variant and only the
  allowed list, versioned by VEKN update date.
- Consequence: card implementation scope is bounded; the format
  data must be re-synced when VEKN publishes updates.

## D-2: Legality by construction (2026-10-08)

- The engine enumerates legal choices at every decision point;
  agents can only pick from them.

## D-3: Digital-first interface (2026-10-08)

- Context: the project architecture centers on a deterministic
  rules engine, explicit decision points, and full game-state
  tracking. This is a strong fit for a digital interface where the
  engine owns the complete state.
- Decision: the default interface target is digital-first, with the
  initial implementation built as a CLI that drives the engine
  directly.
- Consequence: the project will optimize for engine-owned state and
  legal action enumeration rather than a physical-table workflow;
  the latter remains out of scope unless a concrete requirement
  emerges.

## D-4: "Predator cuts" modelled as an automatic RNG draw (2026-10-08)

- Context: 2P variant §3 Game Setup has the predator cut each
  shuffled deck before draws are taken, mirroring the physical-table
  anti-stacking ritual. The rulebook does not say *how* the digital
  engine should represent a "cut" of an already-random, engine-owned
  shuffle.
- Decision: `src/vtesbot/engine/rng.py::GameRNG.cut` performs the
  cut as a second, logged RNG draw (a random cut point), not as a
  `Decision` offered to the predator's agent.
- Rationale: a cut of an already-uniformly-shuffled deck is
  statistically inert -- cutting a uniform random permutation at any
  point yields another uniform random permutation, so a player's
  choice of cut point carries no information and cannot affect the
  outcome. The physical-table purpose of the cut (preventing deck
  stacking by the owner) is already fully guaranteed by the engine's
  trusted seeded shuffle. This is a judgment call about engine
  representation, not a sourced rule, and is recorded here per the
  project's no-guessing philosophy (CLAUDE.md §2) rather than left
  as a bare code comment.
- Consequence: the replay log still records the cut (as a random
  draw) so the step is not silently skipped, but no agent is ever
  asked to choose a cut point. If a future card or ruling ever makes
  the cut point strategically meaningful (e.g. a card that lets a
  player see/influence the cut), this decision must be revisited.

## D-5: Card-hook/registry catalogues are static, not `GameState` (2026-10-09)

- Context: CLAUDE.md §5 says "no global state ... in `engine/`";
  `src/vtesbot/engine/hooks.py` (which hook points exist and which
  card modules answer them) and `src/vtesbot/cards/registry.py`
  (which cards are implemented/blocked) are both module-level dicts
  populated once, at import time, by every
  `src/vtesbot/cards/*.py` module's top-level `register(...)` call.
- Decision: these two catalogues are deliberately *not* fields on
  `GameState`. "No global state" targets the mutable, seeded,
  per-game state (`GameState`, `GameRNG`) that must be deterministic
  and replayable turn-by-turn; a catalogue of which rules the
  engine's `cards/` package knows how to apply is static program
  configuration, identical in kind to
  `src/vtesbot/cards/registry.py`'s own card catalogue (explicitly
  asked for by CLAUDE.md §6: "registry entry"), and does not vary
  within or between games built from the same installed code.
- Consequence: `engine/hooks.py` functions (`offer`, `sum_modifiers`,
  `offer_until_pass`, `resolve_impulse_window`) take the live
  `GameState` as a parameter and only ever *read* game state through
  it (to decide whether a registered provider's option currently
  applies) -- no hook function stores or mutates anything outside
  the `GameState` it is given. Tests that register temporary fake
  providers must remove them afterwards (`hooks.unregister`/
  `hooks.clear`) so the catalogue does not leak between tests, since
  it is shared process-wide state.

## D-6: `docs/OPEN_QUESTIONS.md` capped at 25 entries, overflow archived (2026-10-11)

- Context: each resolved Open Question tends to accumulate a long
  resolution history (follow-up audits, fix rounds, cross-references
  to impacted code/cards), so the file's length grows much faster
  than its entry count. Left unbounded, it becomes expensive to read
  in full for routine work (implementing a card, auditing a rule),
  even though most of its bulk is settled history rather than
  anything still requiring a decision.
- Decision: `docs/OPEN_QUESTIONS.md` holds at most 25 `## OQ-<n>`
  entries at a time. When adding a new entry would exceed the cap,
  the oldest entries still marked `resolved` (never an `open` one)
  are moved verbatim to `docs/open_questions_archive/<NNN>.md` (also
  capped at 25 entries per file), tracked by
  `docs/open_questions_archive/INDEX.md`. OQ numbering stays global
  and is never reused or renumbered by a move. Additionally (2026-10-13):
  the instant an entry's own status flips to `resolved`, its body is
  trimmed to exactly three bullets — Situation / Rules & interactions /
  Solution — dropping the accumulated audit-round narrative, rejected
  alternatives and file-by-file impact lists; its title is updated to
  name the card it blocked wherever one exists. `INDEX.md` carries one
  row per archived `OQ-<n>` (not grouped into ranges), with a `Summary`
  column populated from that trimmed title.
- Rationale: this is an archival/ergonomics decision, not a rules
  question, so it belongs here rather than as an Open Question
  itself. Capping by entry count (not by a token/line budget) keeps
  the rule simple and mechanically checkable (`grep -c '^## OQ-'`);
  archiving only `resolved` entries guarantees nothing still needing
  a decision ever becomes harder to find. The mandatory trim attacks
  this decision's own original Context directly: it was the resolution
  narrative, not the entry count, that made the file expensive to
  read — capping entries alone does not shrink it if each one is still
  150+ lines.
- Consequence: anyone resolving or filing an OQ must check
  `docs/open_questions_archive/INDEX.md` as well as
  `docs/OPEN_QUESTIONS.md` when looking up the highest used `OQ-<n>`
  or an existing entry's current location. See `vtes-rules-reference`
  skill for the exact archive procedure and the exact trim/title
  format.

## D-7: Deck-import pipeline as `formats/`/`decks/`, two judgment calls (2026-10-12)

- Context: milestone 1 ("Deck import + 2P legality check") had no
  runtime implementation at all (`docs/OPEN_QUESTIONS.md` OQ-18 Gap 1
  noted this explicitly) -- only the dev-only
  `scripts/validate_deck.py`/`scripts/krcg_match.py` used to build the
  curated `data/decks/vekn-2p/*.json` fixtures.
- Decision: built `src/vtesbot/formats/` (allowed-list loading +
  legality rules, typed port of `scripts/validate_deck.py::validate`)
  and `src/vtesbot/decks/` (text parsing, name resolution, and
  expansion to `engine.setup.DeckSpec`) per CLAUDE.md §5's own
  architecture table. `scripts/krcg_match.py`'s matching logic moved
  into `decks/name_resolution.py`; the script is now a thin CLI
  wrapper around it, so the dev tool and the production pipeline
  cannot drift apart.
- Two judgment calls made while expanding a resolved decklist into
  real `CryptCard`/`LibraryCard` instances, neither directly stated by
  a cited rule, recorded here per the same no-guessing philosophy as
  D-4:
  1. `LibraryCard.card_type` is read from the live krcg card's own
     `types[0].value`, not from the 2P allowed-list file's `type`
     field -- the allowed-list file only distinguishes `"Crypt"` vs
     `"Library"` (checked across the full `2026-10-03.json`: exactly
     two `type` values appear), too coarse for the engine's existing
     single-granular-type convention (`cards/modius.py`,
     `engine/politics.py`). Every library card in the active 2P pool
     currently prints exactly one krcg type, so `types[0]` is
     unambiguous today; a future multi-type card on the pool would
     need this revisited (same pre-existing simplification `engine/
     cards.py::LibraryCard.card_type`'s own single-`str` shape already
     assumes).
  2. `engine.cards.derive_sect` is only called when the krcg card's
     own `types` includes `"Vampire"` -- gating out Imbued crypt
     cards, per `derive_sect`'s and `CryptCard.sect`'s own documented
     caveat that sect is a vampire-only concept. No Imbued id is
     currently on the 2P allowed list (checked 2026-10-12), so this
     gate is not yet exercised by any real deck, but is needed the
     moment one is added.
- Consequence: a future VEKN 2P update adding a multi-type library
  card or an Imbued crypt card does not silently mis-tag/mis-sect it --
  the first hits judgment call 1 as-is (first-listed type wins,
  revisit if that becomes wrong for a specific card); the second is
  already handled correctly (no sect assigned, matching the existing
  `None`-means-"does not qualify" convention).

## D-8: Heuristic agent v0 rules (design choices, not VtES facts)

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

## D-9: No voluntary self-oust in the 2P duel (2026-10-13)

- Context: OQ-41/OQ-42. The rulebook's Influence Phase "Nora" example
  says she "cannot use both counters in her pool to put that vampire
  into play because that would put her out of the game"; the engine
  offered self-ousting.
- Decision: user ruling (not derived from the rulebook): "à 2 joueurs,
  tu peux tomber à 0 pools à cause de tes actions mais l'objectif étant
  de gagner, on va dire que cela est interdit quelle que soit la
  manière de perdre du pool", and "auto-oust impossible à 2 et 3
  joueurs, possible à 4 et 5 joueurs". A Methuselah never gets an
  option that would bring their own pool to 0 by their own choice;
  `engine/pool.py::can_afford_without_ousting` is the single gate.
  Losses caused by the opponent still oust. Addendum (OQ-43, user
  ruling 2026-10-13: "fame continue de fonctionner normalement car
  aucun choix n'est fait une fois fame en jeu. les choix qui mène
  l'agent lui même à 0 sont interdits"): forced effects with no choice
  at resolution (Fame) still oust normally; any choice whose
  consequence, even downstream (voting against Marcos Belegrad), would
  take the chooser to 0 is not offered.
- Consequence: a deliberate simplification of the 2P duel, to be
  revisited if 4-5 player games are ever in scope.

## D-10: Simultaneous ousts are a tie (2026-10-13)

- Context: OQ-44. Both Methuselahs reaching 0 pool from one event.
- Decision: user ruling (project ruling, supported but not dictated by
  Rulebook §5): "oust simultané semble ok si pas de solution de
  gagner". Same event = tie, no winner; 1 VP each, no 6 pool (§5
  EXCEPTION). "Same event" is mechanical: one card effect or one
  simultaneous strike pair, wrapped in `engine/pool.py::
  simultaneous_pool_losses`.
- Consequence: `MatchResult.winner` may be `None` with `game_over`
  True (`tie`), a draw (user ruling 2026-10-13: "1 VP chacun,
  conclusion = match nul"); sim summaries count ties apart from stuck games. The
  second side of a strike pair still resolves its damage (mend
  decision) before the oust is decided.

## D-11: `FormatConfig.two_player` is a documented but unread flag (2026-10-15)

- Context: `rules-auditor` found that `engine/format.py`'s own docstring
  claims "every 2P-only rule still reads this flag rather than being
  unconditional", but no code anywhere reads `two_player` -- every 2P
  delta (contested crypt cards staying in play, the 3-then-4 transfer
  ramp) is hardcoded unconditionally.
- Decision: accepted simplification, not a bug: CLAUDE.md §1 scopes
  4-5 player VTES out for now, and nothing ever constructs
  `FormatConfig(two_player=False)`, so the flag has no live branch to
  gate. `engine/format.py`'s docstring corrected to describe the
  current, unconditional reality instead of an unbuilt contract.
- Consequence: if 4-5 player support is ever added, every hardcoded
  2P-only call site above must be revisited to actually read
  `state.format.two_player` -- this decision does not pre-build that
  gate, only stops the docstring overclaiming it already exists.

## D-12: Combat Ends and First Strike left unbuilt for 2P (2026-10-15)

- Context: OQ-50 found three Combat Sequence/Strike-Effect primitives
  entirely unbuilt: Combat Ends, First Strike, Steal Blood. Checked
  against the active 2026-10-03 2P allowed list (krcg card text) and
  the 2P variant's own card-exclusion criteria (§2.1, live-fetched
  2026-10-15): Combat Ends has zero matches in the active list and is
  explicitly, permanently excluded by a stated design criterion
  ("combat cards that end combat"); First Strike also has zero matches
  but is not itself a stated exclusion criterion -- its absence is
  incidental to the current list, not guaranteed.
- Decision: both are left unhandled for now, the same way D-11 leaves
  `FormatConfig.two_player` unread -- documented here rather than
  built, since nothing currently needs either.
- Consequence: Combat Ends can be treated as permanently out of scope
  for the 2P format. First Strike must be revisited if a future VEKN
  2P list update adds a card using it (`format-curator`/`sync-2p-format`
  sync should flag this). Steal Blood is **not** covered by this
  decision -- it is live in the current pool (Diversion, Theft of
  Vitae, Form of the Cobra, Hunger of Marduk) and stays tracked as
  OQ-50's own remaining gap.

## D-13: Heuristic agent audit -- phase the roadmap, defer P2/P3 (2026-10-17)

- Context: an external audit report proposed a four-tier roadmap for
  `agents/heuristic.py` -- P0 (benchmark/instrumentation reliability), P1
  (contextual heuristics: bleed/hunt, recruitment, blood/pool allocation),
  P2 (a `score(state, action)` evaluation function + limited lookahead),
  P3 (card-specific evaluators + calibration on a held-out seed set). The
  report was checked against the actual code, not taken at face value: its
  "always bleed" claim doesn't hold (`_action` already branches on
  `LOW_BLOOD`, pinned by
  `tests/agents/test_heuristic.py::test_bleeds_with_blood_and_hunts_when_low`),
  but the absence of any scoring abstraction and of economic detail in
  `sim/report.py`'s `batch_results.csv` is accurate.
- Decision: implement only the report's P0 (benchmark instrumentation --
  economic counters, a heuristic-vs-heuristic self-play baseline, a
  position-swap check, wider decision-log sampling) and the generic,
  non-card slice of P1 (a lethal-bleed floor on `action_choice`, pool-aware
  scoring for `bring_crypt`/`add_blood`/`remove_blood`) now, as milestone 5
  work. P2 (lookahead/minimax) and P3 (card-specific evaluators, ML-style
  calibration) are explicitly deferred, not built:
  1. P2 needs a capability CLAUDE.md §8 already flags as an open,
     deliberately unsettled architecture decision (heuristics vs
     determinized MCTS/ISMCTS vs RL, reserved for milestone 7). Building a
     lookahead now means making that call ad hoc inside `agents/`, most
     likely requiring an engine-level state-clone/determinization
     primitive that blurs the "pure core" boundary (CLAUDE.md §5) and
     would itself need `rules-auditor` review as a core-engine change.
  2. P3 needs a card pool milestone 6 ("full 2P allowed list") hasn't
     finished building yet -- card-specific evaluators written against a
     partial registry would need rewriting as more cards land, and the
     report's own calibration method (train/validate on separate seed
     sets, check generalization to unseen configurations) has nothing
     stable to generalize against until milestone 6 is done.
- Consequence: a future revisit of P2 belongs with milestone 7 (with its
  own `score`/lookahead decision entry then); a future revisit of P3
  belongs after milestone 6. Phase A/B's own concrete thresholds
  (lethal-bleed floor, pool-aware recruit scoring) get their own decision
  entry once implemented, following D-8's framing (design choices, not
  VtES facts).

## D-14: Heuristic agent Phase B thresholds (design choices, not VtES facts)

- Context: D-13's Phase B -- the generic, non-card slice of the audit
  report's P1 -- on `agents/heuristic.py`. All thresholds below are
  untested assumptions (D-8's own framing), not community strategy
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
  200 versus`/`... 200 selfplay`, same seed range as D-13's Phase A
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
  from D-8): blocks, combat steps, damage mending, votes, contest
  resolution, edge gain, card-specific targets; `master_phase_action`'s
  "play first offered card" and `minion_phase_choice`'s "highest blood
  vampire first" are also unchanged by this entry.
- Addendum (2026-10-17), considered and deferred: `discard_phase_action`
  always passes (D-8 item 4), forfeiting a once-per-turn discard+redraw
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
  benchmark. Deferred to milestone 6/7 alongside the rest of D-13's P3.
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
  (seeds 0-199, same commands as above) against the D-14 baseline:
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
  parallel" is exactly the kind of thing D-13 defers to milestone 7.

## D-15: `action_choice` beyond bleed/hunt (design choice, not a VtES fact)

- Context: an external review of the D-13/D-14 delivery found that the new
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
  existing lethal-bleed `inf` override (D-14) still wins over everything.
  This is deliberately card-blind, matching D-13's P3 deferral: the agent
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
  200 versus`/`... 200 selfplay`, same seed range and deck as D-13/D-14):

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
  regression by D-14's own keep/revert rule. Reverted in favor of the
  two-tier version above, which never outranks an ordinary bleed.
- Addendum (2026-10-17), lost self-play games audited, nothing else acted
  on: sampled a batch of 200 self-play games (`sim.runner.run_many` with
  `report_sample_losses_and_ties=True`) and read several losing games'
  decision logs (`sim/report.py::format_decision_log`). One recurring
  pattern: in some losses, one side's `minion_phase_choice` offers only a
  single `act_with:` vampire for many turns in a row while the other side
  accumulates two or three, because `_score_bring_crypt`'s existing
  `has_uncontrolled` gate (D-14) keeps directing every transfer into
  whichever single uncontrolled vampire already exists until it reaches
  capacity rather than ever starting a second one in parallel -- this is
  the exact trade-off D-14's own "tried and reverted" `bring_crypt`
  addendum already investigated and found to regress the benchmark; not
  re-attempted here, left as a P2/lookahead-grade question (D-13) about
  when starting a second vampire in parallel is worth it. No other
  generic, card-blind, cheaply-benchmarkable weakness was found in this
  sample: `block_attempt`, `strike_choice`, `mend_damage`, `press`,
  `maneuver_choice`, `additional_strike_choice`, `edge_pool_gain`,
  `contest_resolution`/`master_card_contest_resolution`,
  `wider_view_remove_target`, and `end_of_round` all still fall back to
  random play, exactly as D-8/D-14 already document -- reconfirmed, not a
  new finding, and out of this entry's scope.
