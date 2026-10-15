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
