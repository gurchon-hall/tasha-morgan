# Open questions

Rules or card interactions that the official sources do not settle.
Nothing listed here may be implemented by guessing. Format and
procedure: see `.claude/skills/vtes-rules-reference/SKILL.md`. A
resolved entry is trimmed to Situation / Rules & interactions /
Solution only, with its title tied to the card it blocked wherever
one exists.

Capped at 25 entries (`docs/DECISIONS.md` D-6). Older `resolved`
entries live in `docs/open_questions_archive/` once this file fills
up — check `docs/open_questions_archive/INDEX.md` too when looking
up an OQ number or the highest one used so far.

## OQ-16: "Cannot contest yourself" unimplemented on both paths (status: open)

- Situation: found by `rules-auditor` while reviewing OQ-10/OQ-14's ally
  contest-detection fix. Not a ruling ambiguity -- re-fetched live
  (<https://www.vekn.net/rulebook/4-detailed-turn-sequence>, "Contested
  Cards" DECK CONSTRUCTION caution box, cross-checked against the local
  cache `data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md`),
  quoted verbatim: "You cannot control more than one of the same unique
  card at a time, and you cannot voluntarily contest cards with yourself
  (if some effect would force you to contest a card with yourself, then
  you simply burn the incoming copy of the unique card)." Plain and
  explicit.
- What's missing: both `engine/contests.py::detect_contest_on_reveal`
  (pre-existing, vampire/crypt-card side) and `engine/allies.py::
  detect_contest_on_recruit` (new, OQ-10's own fix) only ever check the
  *opponent's* same-named minions for a collision, never the acting
  player's own. Neither function, nor any deck-legality check, currently
  prevents or reacts to one Methuselah controlling two live copies of the
  same unique card at once -- confirmed live by
  `tests/rules/test_ally_contests.py::
  test_a_players_own_two_allies_of_the_same_name_do_not_contest_each_other`,
  which asserts both copies end up simultaneously `zone == "ready"` with
  `contested_with is None`, directly contradicting the quoted rule's "you
  cannot control more than one... at a time."
- Why this is open, not yet fixed: not a new gap introduced by OQ-10's own
  pass -- it mirrors `detect_contest_on_reveal`'s pre-existing scope
  boundary exactly (an existing, unaudited gap on the vampire side,
  confirmed by `rules-auditor`'s review). Currently unreachable in a real
  game: no card can yet recruit a second copy of its own unique ally, and
  no deck-legality/`format-curator` check yet exists to even flag two
  copies of the same unique vampire in one crypt (milestone 1 scope, not
  yet built). Flagged now, before any future card or deck-validation
  feature makes it reachable, so it is tracked as a known gap rather than
  silently inherited.
- What would be needed: when a same-named collision check runs (on reveal
  for a vampire, on recruit for an ally), also check the *acting player's
  own* existing same-named minions in play; if found, burn the incoming
  copy immediately per the quoted rule ("you simply burn the incoming copy
  of the unique card") rather than leaving both live or routing it through
  the normal opponent-contest flow. `rules-engineer` scope
  (`engine/contests.py`, `engine/allies.py`).
- Impacted code: `src/vtesbot/engine/contests.py::detect_contest_on_reveal`,
  `src/vtesbot/engine/allies.py::detect_contest_on_recruit`. Impacted
  cards: none yet reachable (tracked ahead of need, same spirit as OQ-10's
  own original "latent, flagged before live" framing).

## OQ-17 - Enchant Kindred - no action-card entry point (status: resolved)

- Situation: Enchant Kindred (100640, `types==["Action"]`) is itself
  the acting vampire's whole minion action for the turn — but the
  engine had no generic way for a played library card to supply its
  own alternate minion action (only Bleed/Hunt/Recruit-Ally were
  wired into `_choose_and_perform_action`).
- Rules/interactions: plain text; faking it as an Action-Modifier on a
  separately-chosen bleed would wrongly let the vampire bleed for free
  and play the card as a bonus. "A younger vampire" (superior clause)
  reads, per the project owner, as younger than the acting vampire,
  matching the unqualified-comparative convention other cards' texts
  use.
- Solution: added `ACTION_CARD_PLAY_HOOK`/`ActionCardSpec` (base
  stealth, directed/undirected, `resolve`, optional `on_blocked`, and
  an `action` field so a clause can declare its real mechanical
  identity, e.g. `ACTION_BLEED`, so it doesn't silently suppress
  another card's bleed-gated provider sharing the window), offered
  alongside the existing top-level choices. Enchant Kindred was then
  implemented: basic clause as a +2 bleed tagged `ACTION_BLEED`;
  superior clause raises a plain "pick an eligible uncontrolled
  vampire" decision and adds blood via `effective_capacity` (OQ-8).
  `Status.IMPLEMENTED`.

## OQ-18 - Dust Up - no sect, no dodge/extra strike (status: resolved)

- Situation: Dust Up (100597, "Requires an Anarch", three discipline
  clauses) was blocked by two independent gaps: (1) the engine had no
  vampire-sect concept at all, and (2) the `[cel]` clause ("dodge,
  with 1 additional strike (limited)") needed dodge and same-round
  additional-strike mechanics `engine/combat.py` didn't have.
- Rules/interactions: Rulebook §6 Vampire Sects + §7 (Laibon) name the
  five sects; §4 Combat's Choose Strike / Additional Strikes sections
  cover dodge and repeat strikes; [LSJ 20030902-2]/[LSJ 20060808-1]
  confirm a dodge-proof strike ("cannot be dodged") still lets the
  opponent dodge, it just has no effect against that one strike.
- Solution: added `Sect` enum + `CryptCard.sect` + `derive_sect
  (card_text)` (a regex classifier over the printed sect preamble,
  100% hit rate across the full krcg crypt dataset; raises
  `UnresolvedRulingError` rather than guessing on a non-match). Added
  `COMBAT_DODGE_OPTION_HOOK` (zeroes the opponent's simultaneous
  damage unless the attacking strike is flagged
  `StrikeDamage(ignore_dodge=True)`) and
  `COMBAT_ADDITIONAL_STRIKE_HOOK` (re-enters the full strike-choice
  machinery). Dust Up was then implemented (all three clauses, gated
  on `sect is Sect.ANARCH`); the `[cel]` "(limited)" cap was initially
  enforced per-vampire-forever rather than per-round (stricter than
  the rule, never looser) until OQ-19 fixed this properly with shared
  round-scoped state. `Status.IMPLEMENTED`.

## OQ-19 - Cross-card "(limited)" additional-strike cap not pooled (status: resolved)

- Situation: Dust Up and Side Strike each tracked their own
  "(limited)" additional-strike cap privately per-card,
  per-vampire-instance — so nothing stopped one vampire from using
  *both* cards' grants in the same round (an illegal-play risk), and
  the cap never reset between rounds.
- Rules/interactions: SS8 glossary, verbatim: "A minion cannot use
  more than one card or effect to gain additional strikes per round
  of combat."
- Solution: `run_combat` now creates a fresh, round-scoped
  `round_state` dict threaded into the dodge/additional-strike hook
  contexts; `additional_strike_limit_used`/
  `mark_additional_strike_limit_used` read/write a shared flag in it
  (degrading gracefully when offered outside `run_combat`). Both cards
  were migrated onto the shared helpers. A `rules-auditor` follow-up
  found and fixed a regression in the first landing: the flag was
  briefly a single flat boolean shared across *both* combatants,
  wrongly pooling the cap jointly instead of per-minion — fixed by
  keying it per `context["vampire"]`.

## OQ-20 - Vote/ballot casting order for two Methuselahs (status: resolved)

- Situation: the rulebook's "cast ... in any order" leaves the actual
  turn structure unspecified; the engine's first implementation
  asserted its own strict "impulse always returns to the caller"
  procedure was sourced from the general impulse rule, when it was
  not — that procedure in fact gave the caller an unsourced tactical
  edge (casting every source back-to-back before the opponent ever
  got a look).
- Rules/interactions: no official text specifies an
  alternation/priority rule for vote-casting order beyond "in any
  order."
- Solution (user ruling, from real-table play experience): votes are
  cast in table order — seating order, repeating laps until a full
  lap passes with nobody casting. In this 2P engine: a fixed two-seat
  rotation, caller first each lap, alternating strictly after every
  step (cast or pass) regardless of who just acted; a full lap
  completing with no casts (`consecutive_passes` reaching 2) closes
  the window.

## OQ-21 - Action-card target chosen at announce vs. resolve time (status: resolved)

- Situation: `line_brawl.py`'s `[pot]` clause ("Enter combat with a
  minion") picked its target inside `resolve()`, after the
  block-attempt window had already run — the defender was asked to
  block before the specific minion that would be forced into combat
  was ever fixed.
- Rules/interactions: Rulebook §4 "Announce the Action": "All details
  of the action are defined when the action is announced, including
  the target(s)"; this engine's own `ActionCardSpec` contract already
  documented the same. The general "fizzle" ruling (target no longer
  eligible at resolve time ⇒ cost paid, successful, no effect — never
  re-picked) confirms a target is fixed once, at announce, and only
  re-validated later.
- Solution: both `line_brawl.py` and `enchant_kindred.py`'s own
  clauses now choose their target inside `apply()` (announce time),
  with `resolve()` only looking up the already-chosen id. Any future
  Action card targeting a specific minion must do the same.

## OQ-22 - Fame - contested cards gap beyond crypt/ally (status: resolved)

- Situation: Fame (100698, Unique master card attached via
  `CardAttachment`) has the same "two independently-built decks could
  both play a copy" exposure OQ-10 already fixed for allies, but
  `CardAttachment` had no contest tracking of its own at all.
- Rules/interactions: the same unified Contested Cards mechanism
  (OQ-10/OQ-15) applies unmodified to an attached Unique master card —
  the 2P crypt-card override does not reach it.
- Solution: `CardAttachment` gained `controller`/`instance_id`/`zone`/
  `contested_with` (no longer frozen); `engine/attachments.py::
  attach_card`/`detect_contest_on_attach`/
  `resolve_one_attachment_contest` mirror the ally-side functions;
  `unlock.py` extended with a `"contest_attachment:"` branch. A
  contest is tracked against the attachment's own *controller* (who
  played it), not the host vampire's controller — clarified in a
  follow-up addendum after a `rules-auditor` finding that the initial
  docstring overclaimed the Master-card controller rule as if it
  covered a future Equipment/Retainer attachment too (it doesn't —
  those follow the Minion-card controller rule instead; corrected by
  documentation only, no card uses this yet). Fame itself stays
  `blocked`.

## OQ-23 - Oxford University - standalone master-card entity (status: resolved)

- Situation: Oxford University, England (101341, "Unique location...
  lock this card and burn X pool during the polling step... to get
  +2X votes") needed a generic "a Master card that stays in play,
  mutable, rather than attaching or resolving once" entity, which did
  not exist. First widened from "a standalone *Unique* location" to
  any standalone Master card, Unique or not, after the project owner
  pointed to Wider View (102180, no "Unique" clause, same shape).
- Rules/interactions: "location" is not a structured krcg card type —
  "Unique location." is free text on an ordinary Master card. A sweep
  of the full 2P allowed list found 18 cards sharing this shape (17 of
  them Unique). Contested Cards (OQ-10/15/22) applies unmodified to
  the Unique subset.
- Solution: added `MasterCardInPlay`/`engine/master_cards.py`
  (`bring_master_card_into_play`, `detect_contest_on_bring_into_play`
  — called only for cards actually printed Unique,
  `resolve_one_master_card_contest`), unlock-phase lock/unlock +
  delayed-restore wiring, `MasterCardView`/`Observation.master_cards`,
  and `engine/politics.py::variable_pool_burn_vote_options` (the
  reusable "burn X pool for Y·X votes" polling-step primitive Oxford's
  own ability needs). Deliberately not built: a `counters` field
  (needed by 6 of the 18 sweep cards) and an opponent-burn/steal
  primitive (needed by 4 more) — flagged for whichever future pass
  needs them. Oxford itself, and the other 17 sweep cards, stay
  unimplemented.

## OQ-24 - Wider View - no influence hook, no removed zone (status: resolved)

- Situation: Wider View (102180, Trifle, in-play via OQ-23's new
  entity)'s two transfer-costed clauses ("use 1 transfer to draw from
  crypt and remove a crypt card from the game"; "use 4 transfers to
  burn this card and gain 2 pool") needed the Influence phase to be
  card-hookable (it was a closed, hardcoded implementation) and a
  "removed from the game" zone distinct from "burned" (needed because
  the ruling "[c]ards removed from the game are public" [LSJ
  20080314] only matters for a card that may still be
  face-down/unrevealed at removal time).
- Rules/interactions: plain text and ruling; not an ambiguity.
- Solution: added `INFLUENCE_PHASE_ACTION_HOOK`, offered in
  `influence_phase` alongside the three hardcoded transfer types;
  added `Zone` value `"removed_from_game"` and
  `engine/damage.py::remove_vampire_from_game` (already public by the
  existing `visible_identity` rule, confirmed — no further Observation
  change needed). A `rules-auditor` follow-up found and fixed a MAJOR
  silent-mis-resolution risk: a hook-provided choice could collide in
  value with one of the three hardcoded choices and silently take over
  that action — fixed with a new general `hooks.
  ensure_unique_choice_values` guard (raises instead of silently
  misrouting), called wherever hook and hardcoded choices are unioned.
  Wider View's own card module is not written; both engine gaps are
  resolved.

## OQ-25 - Fleetness - no pre-combat maneuver grant (status: resolved)

- Situation: Fleetness's (100747) superior clause grants a vampire "1
  optional maneuver during that combat" from the moment the card is
  played (announce time) — before whichever combat the action
  produces has even started — but `run_combat` always starts its
  scratch state fresh and empty, with no way for an action resolving
  before combat starts to pre-seed a grant into it.
- Rules/interactions: plain text; the generic OQ-21 fizzle convention
  already covers the target-unlocked-by-resolve-time case. A
  card-module-only scratch dict was rejected as it would live outside
  `GameState`, breaking the determinism/replay invariant.
- Solution: `run_combat` gained an optional `initial_combat_state`
  parameter; `seed_pre_combat_maneuver_grant`/
  `pre_combat_maneuver_available`/`consume_pre_combat_maneuver_grant`
  are the shared helpers (a count, not a bool, so grants compose by
  addition). `ActionCardSpec` gained a `maneuver_grant` field threaded
  through both the unblocked path (a card's own `resolve()` seeds its
  direct `run_combat` call) and the blocked path
  (`perform_minion_action` seeds its own internal call). Fleetness's
  own card module is not written; the primitive is complete.

## OQ-26 - Organized Resistance - no forced-block hook (status: resolved)

- Situation: Organized Resistance (102230)'s second clause unlocks a
  locked Anarch to force an unconditional block attempt with +1
  intercept, bypassing the normal "only when needed" ping-pong —
  `attempt_block`'s candidate list was hardcoded to ready-unlocked
  vampires only, with no way to inject a locked one, unlock it on
  choice, or skip the ping-pong.
- Rules/interactions: rulings on file ([LSJ 20090514],
  [ANK 20181122-2], [LSJ 20010714-2], [ANK 20180623]) confirm the
  block and any resulting combat happen unconditionally once chosen,
  and normal prey/predator/target restrictions still apply (already
  structurally satisfied by the 2P single-opponent collapse, OQ-1).
- Solution: added `BLOCK_CANDIDATE_INJECTION_HOOK`, offered inside
  `attempt_block`'s retry loop alongside the hardcoded ready-unlocked
  candidates (unioned via `ensure_unique_choice_values`); a chosen
  injected option's `apply` unlocks the vampire and is returned
  directly as the blocker, never routed through the stealth/intercept
  ping-pong. The first clause (+1 intercept to an Anarch) is a plain,
  clean `"intercept_modifier"` provider needing no new mechanism. Card
  module itself is not written; the mechanism is complete.

## OQ-27 - Pursuit - maneuver/strike bundling question (status: resolved)

- Situation: Pursuit (101523, "[cel] Maneuver. / [CEL] Additional
  strike (limited).") was initially assumed to be a "maneuver from a
  strike card" (Rulebook §4: using such a maneuver commits that
  combatant's strike choice for the round, and bars a second strike
  card from maneuvering again the same round) — a shape the engine
  had no mechanism for.
- Rules/interactions: two owner-raised leads were checked against
  sources, and the second held up: the Rulebook's own Choose Strike
  section specifies the commit/cap only applies to a maneuver "from a
  strike" — i.e. bundled in the same clause as a strike effect
  (Slam's "as above", .44 Magnum's "with 1 optional maneuver...
  Strike:"). Pursuit's bare "[cel] Maneuver." clause, textually
  separate from its unrelated "[CEL] Additional strike" clause, is not
  that shape.
- Solution: Pursuit needed no new engine mechanism after all —
  implemented directly against the existing `MANEUVER_HOOK` (plain
  grant, no strike-lock, no per-combat bookkeeping) and
  `COMBAT_ADDITIONAL_STRIKE_HOOK`. `Status.IMPLEMENTED`. Slam and .44
  Magnum remain the genuine, still-unbuilt "maneuver from a strike"
  examples (tracked by OQ-28); `engine/combat.py`'s own docstring
  should be corrected to drop Pursuit from that list in a future pass.

## OQ-28 - Slam - maneuver committing a strike (status: resolved)

- Situation: Slam's (101798) superior clause bundles its maneuver with
  its own "hand strike at +2 damage" effect ("as above") — a genuine
  "maneuver from a strike" (per OQ-27's resolution): using it must
  commit that combatant's one strike choice for the round to this same
  effect, with no independent later choice. No mechanism existed for a
  maneuver grant to pre-commit the strike step.
- Rules/interactions: Rulebook §4 Choose Strike, verbatim, quoted in
  OQ-27's own resolution; [LSJ 20021028] confirms the maneuver and
  strike are not independent for this card.
- Solution: added `COMMITTED_STRIKE_KEY` inside the round-scoped
  `round_state`; `commit_strike_for_round(context, strike)` (called
  from a strike-bundled `MANEUVER_HOOK` provider's own grant; raises
  if called twice for the same vampire the same round, or if its
  choice-value collides with a built-in strike value); `_ask_strike`
  pops (not reads) the commitment before offering anything, locking
  only the *initial* strike of the round, not a later additional
  strike. A plain, non-strike-bundled maneuver (Saku, Pursuit, Dance
  with the Devil, Fleetness) is unaffected. Slam itself was then
  implemented against this mechanism (both clauses).
  `Status.IMPLEMENTED`.

## OQ-29 - Taste of Vitae - no end-of-round window (status: resolved)

- Situation: Taste of Vitae (101945, "only usable at the end of a
  round of combat... gains blood equal to the amount of blood lost by
  the opposing vampire to damage this round") needed two missing
  mechanisms: an End of Round hook/window (Rulebook §4 step 7), and a
  round-scoped "blood lost specifically to damage this round"
  accumulator (distinct from a vampire's raw blood deficit, which
  could reflect unrelated effects).
- Rules/interactions: rulings on file confirm it's playable after a
  round ends prematurely, before/after other end-of-round effects, and
  even if the opponent was burned (so the accumulator must stay
  readable after a burn).
- Solution: added `Hook.END_OF_ROUND`/`END_OF_ROUND_HOOK`, dispatched
  exactly once per round on every exit path via a restructured round
  loop (`still_ready`/`pressed` booleans replacing scattered
  `break`s), offered as a real two-sided repeatable impulse window
  (not a single binary ask like press). Added `BLOOD_LOST_TO_DAMAGE_
  KEY` inside `round_state`, written by `apply_damage`'s mend and
  aggravated-burn branches via `record_blood_lost_to_damage`, queried
  via `blood_lost_to_damage_this_round`. Taste of Vitae itself was
  then implemented against both (per-round per-vampire play cap,
  zone/hand gates, reading the opponent's own blood-loss record fresh
  at apply time). `Status.IMPLEMENTED`.

## OQ-30 - Perfect Paragon - no intercept-decrease hook (status: resolved)

- Situation: Perfect Paragon's (101387) superior clause ("Allies and
  younger vampires get -1 intercept") is played by the *acting*
  vampire to weaken a potential blocker's intercept, proactively and
  persisting for the whole action ([LSJ 20020612]: usable any time
  before resolution, no block attempt required) — but
  `INTERCEPT_MODIFIER_HOOK` is only ever offered to the *defender*,
  once a specific candidate is already fixed, as a one-shot delta. A
  sweep found 16 other unimplemented cards sharing this exact shape.
- Rules/interactions: the Rulebook glossary's Action Modifier
  definition and the quoted ruling settle who plays it and when; the
  rulebook's own stealth/intercept duration sentence means the effect
  should persist and re-apply to every later-chosen qualifying
  candidate, not just one fixed at activation time.
- Solution: added `INTERCEPT_DECREASE_HOOK`, offered to the actor at
  the top of `attempt_block`'s retry loop (before any candidate
  exists, giving OQ-11's "re-offered on retry" for free); a provider's
  `apply` appends an `ActiveInterceptDecrease(delta, qualifies)`
  predicate (never itself exposed to an agent) to `pending`;
  `_duel_stealth_intercept`'s intercept baseline is now the sum of
  every recorded modifier whose predicate matches the currently-fixed
  candidate, recomputed fresh each call (never floored at 0, per the
  rulebook). Perfect Paragon itself and the rest of the family stay
  unimplemented; the mechanism is complete. See OQ-31 for a scoping
  question this entry's own first landing left open.

## OQ-31 - Perfect Paragon family - proactive-only or also reactive (status: resolved)

- Situation: OQ-30's mechanism only offers `INTERCEPT_DECREASE_HOOK`
  proactively (before a candidate is fixed, or on a retry) — never
  reactively, at the exact impulse-return moment inside the ping-pong
  where a specific candidate is already fixed and about to succeed.
  The rulebook's general "any time before resolution" Action Modifier
  timing rule doesn't itself settle whether that entitles a reactive
  offer too.
- Rules/interactions: no source draws the proactive/reactive
  distinction explicitly; two readings were open (A: proactive-only is
  sufficient; B: a reactive offer is also required).
- Solution (user ruling, same precedent as OQ-20): Reading B — both
  opportunities coexist. `_duel_stealth_intercept`'s reactive branch
  now offers `INTERCEPT_DECREASE_HOOK`'s options merged into the same
  `Decision` as `STEALTH_MODIFIER_HOOK` (mirroring how `_ask_strike`
  already merges strike/dodge options for one offer point), under the
  pre-existing `"stealth_modifier"` decision kind so every pre-OQ-31
  test is unaffected when no decrease provider is registered. A
  reactively-activated modifier is recorded into the same persistent
  `pending` list as a proactive one, so it composes identically with
  OQ-11's retry case.

## OQ-32 - Diana Iadanza - no "cancel as played" hook (status: resolved)

- Situation: Diana Iadanza (201694): "During a referendum she calls,
  Diana can burn 1 blood to cancel a reaction card as it is played
  (cost is still paid). +1 bleed." Found implementing this card (the
  "+1 bleed" clause needed no new engine work and is implemented
  separately): `Hook.CANCEL_AS_PLAYED` was named for classification
  only, with no dispatch call site anywhere — every Reaction card
  implemented so far resolves its entire effect atomically inside one
  `HookOption.apply()`, with no "announced, not yet resolved" moment
  for a third party to inject a cancellation.
- Rules/interactions: generic rulings on file for "cancel a card as it
  is played" ([LSJ 20061207]/[RBK playing-a-card]/[LSJ 20061013],
  [LSJ 20080630]/[LSJ 20011023], [ANK 20190104]/[RBK cancel-a-card]/
  [LSJ 19980212], [LSJ 20030224], [LSJ 20060106]) already fully
  specify the mechanic: played immediately, no other effects
  interleave; cost still paid; a "do not replace until" clause is also
  canceled; the card still counts as played (same-reaction-once-per-
  action still applies); a canceled limited effect does not trigger
  its own limit.
- Solution: a missing engine primitive, not an unsettled ruling. Added
  `engine/hooks.py::apply_chosen_option(state, option, played_by,
  may_cancel, context)`, sitting between "a `HookOption` is chosen"
  and "its effect runs," for both generic decision-loop helpers
  (`offer_until_pass`, `resolve_impulse_window`). `HookOption` gained
  an optional `cost` callable (runs unconditionally before any
  cancellation offer, keeping "cost is still paid" true even when the
  effect itself is suppressed); after `cost` runs, the *other* side is
  offered `CANCEL_AS_PLAYED_HOOK` once; choosing a cancellation runs
  its own `apply` and suppresses the original entirely.
  Zero-behaviour-change with no provider registered. A `rules-auditor`
  follow-up found and fixed a live landmine: Telepathic Counter's own
  `apply` atomically combined its cost (play-from-hand, SS8 "used"
  bookkeeping) with its actual effect — split into `cost`/`apply` so a
  future cancellation can't also undo the card having been played.
  Organized Resistance/Protection Racket have the same atomic pattern
  but aren't yet exposed to `apply_chosen_option` — flagged for
  whoever wires their dispatch sites through it next. Diana Iadanza's
  own card module is not written for clause 1 — stays
  `blocked`/`OQ-32`; her "+1 bleed" clause is implemented separately.

## OQ-33 - Diana Iadanza - no cancel-type marker (status: resolved)

- Situation: OQ-32 (resolved) built `engine/hooks.py::apply_chosen_option`
  but left `cancel_context` carrying no structured marker of the canceled
  option's own card type -- Diana's clause 1 ("Diana can burn 1 blood to
  cancel a *reaction card* as it is played") needs exactly that marker, to
  tell a genuine Reaction-card play apart from the same referendum-phase
  window's other, non-Reaction providers (Modius's discard-a-master-card
  ability, Oxford University, England's polling-step burn).
- Rules/interactions: a missing engine primitive, not a ruling question.
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

## OQ-34 - Loup - no action-succeeded signal or turn card (status: resolved)

- Situation: Loup (krcg id 102273, Action Modifier, Toreador): "Only one
  Loup can be played each turn. Put this card in play. Toreador get +1
  stealth. Burn this card at the end of the turn or after a Toreador
  performs a successful action." Needed two missing primitives: a generic
  "this action just succeeded" signal (independent of whether the
  action's own effect did anything), and a "stays in play for the rest of
  the turn, until burned" entity distinct from both `CardAttachment` and
  the cross-turn `MasterCardInPlay`.
- Rules/interactions: Rulebook §4 "Resolve the Action" (re-fetched live),
  verbatim: "An action is successful only if it is not blocked" / "If the
  action is successful (all block attempts were unsuccessful), then the
  cost of the action is paid and the effects of the successful action
  take place" — success is purely "not blocked." "The turn" in Loup's own
  burn clause is unambiguous: VTES turns are strictly sequential (never
  two in progress at once), and this card can only ever be played by its
  own controller's own acting Toreador vampire, so "the turn" and "the
  controller's own turn" coincide by construction — no further question
  needed on that sub-point.
- Solution: added `engine/action.py::ACTION_SUCCEEDED_HOOK`
  (`cards/registry.py::Hook.ACTION_SUCCEEDED`), dispatched via
  `hooks.run_effects` immediately after `perform_minion_action`'s own
  `resolve(pending)` call returns (never on the blocked branch), carrying
  `actor_player`/`vampire`/`action`. Added `engine/state.py::
  TurnCardInPlay`/`PlayerState.turn_cards` and `engine/turn_cards.py`
  (`bring_turn_card_into_play`/`burn_turn_card`/`active_turn_cards`/
  `clear_turn_cards_at_end_of_turn`, the last wired into `engine/phases/
  turn.py::play_turn` right before the turn flips). Loup's own card module
  (`cards/loup.py`, `Status.IMPLEMENTED`) was written in a later pass; see
  its own docstring for the "only one Loup per turn" cap and a
  self-documented timing gap against the "can be used even if the stealth
  is not currently needed" ruling.

## OQ-35 - Disputed Territory - no location control-transfer (status: resolved)

- Situation: Disputed Territory (krcg id 100557, Political Action):
  "Choose a location and a Methuselah. Successful referendum means the
  chosen Methuselah takes control of the chosen location." Needed a
  generic way to change who controls an existing in-play "location" — a
  concept OQ-23 already found is not a distinct krcg type, but free text
  on either a standalone Master card or an attached Equipment.
- Rules/interactions: rulings on file via krcg, verbatim: "If used to
  steal an equipment representing a location, it can be placed on any
  minion controlled by the new controller" [RTR 19960112]; "Changing the
  controller of a location has no other effect, unless specified by card
  text. Exception: A location 'on' another controlled card is moved onto
  an appropriate card controlled by the new controller of the location"
  [RTR 19980623]; "If used to 'change' the control of a location... to
  the same Methuselah, the location cannot be moved to another minion
  controlled by the same Methuselah" [LSJ 19971002].
- Solution: added `engine/attachments.py::transfer_attachment_control`
  (always re-hosts onto a caller-supplied destination vampire, per the
  Exception clause — an attached card is always "on" a vampire; rejects
  a same-controller call whose `new_host` is not the attachment's own
  current host, per [LSJ 19971002] — a `rules-auditor` finding fixed
  after this entry's first landing omitted that clause entirely) and
  `engine/master_cards.py::transfer_master_card_control` (never re-hosts a
  standalone card, only moves it between `PlayerState.master_cards` dicts
  and reassigns `controller`). Which destination vampire/controller to use
  is left to whichever future card module calls these (its own `Decision`,
  not built here). Disputed Territory's own card module (`cards/
  disputed_territory.py`, `Status.IMPLEMENTED`) was written in a later
  pass.

## OQ-36 - Voter Captivation - no post-resolution dispatch (status: resolved)

- Situation: Voter Captivation (krcg id 102131): "Only usable after
  resolution of a political action whose referendum passed. [pre] This
  vampire gains 1 blood for each vote by which the referendum passed."
  `cards/registry.py::Hook.REFERENDUM_RESOLVED` was reserved for exactly
  this moment but had no engine dispatch call site — a moment strictly
  after a political-action card's own `resolve()` closure (which itself
  calls `resolve_referendum` and then runs its own pass effects) fully
  returns, later than `POLLING_STEP`/`REFERENDUM_TALLIED`.
- Rules/interactions: a missing engine primitive, not a ruling question —
  the hook's own trigger semantics were already settled when it was
  named/reserved (its own docstring).
- Solution: `engine/politics.py::resolve_referendum` gained an optional
  `action_pending` parameter, writing its own tally/pass-fail outcome into
  `REFERENDUM_RESULT_KEY` inside whatever dict it is given (never its own
  internal polling-step `pending` scratch); `cards/kine_resources_
  contested.py`/`cards/parity_shift.py` now pass their own `resolve()`
  closure's `pending` through as `action_pending` (both still
  `Status.IMPLEMENTED`, no new provider registered). `engine/action.py::
  perform_minion_action` dispatches the new `REFERENDUM_RESOLVED_HOOK`
  (`hooks.resolve_impulse_window`, a real two-sided window — unlike
  `ACTION_SUCCEEDED_HOOK`, this is a card a player chooses to play) right
  after its own `resolve(pending)` returns, only when `action ==
  ACTION_POLITICAL` and the referendum passed; context carries
  `caller`/`other`/`caller_vampire_id`/`margin`/`pending` (the last added
  in a later pass, a per-action once-per-minion cap, `rules-auditor`
  finding). Voter Captivation's own card module (`cards/
  voter_captivation.py`, `Status.IMPLEMENTED`) was written in a later
  pass.

## OQ-37 - Scalpel Tongue - no mid-cast vote cancellation (status: resolved)

- Situation: Scalpel Tongue (krcg id 101686): "Only usable during the
  polling step of a political action. [cel][pre] Choose a vampire who has
  cast votes or ballots in this referendum. The chosen vampire is locked
  and abstains (this cancels the chosen vampire's votes and ballots)."
  Needed a way to retroactively undo an already-cast vote source mid-way
  through `_cast_votes`'s own casting loop — distinct from
  `pending["forced_abstain"]` (OQ-6), which only ever prevents a future
  cast, applied once before casting begins.
- Rules/interactions: ruling on file, "Cannot be used during a referendum
  that is automatically passing" [PIB 20150105]/[LSJ 19980107] — not
  itself built (no auto-passing mechanism exists in the engine yet, per
  OQ-6's own note); otherwise a missing engine primitive, not a ruling
  ambiguity.
- Solution: `engine/politics.py::_cast_votes` now also offers
  `POLLING_STEP_HOOK` on every player's own turn in the existing
  table-order rotation (OQ-20), under a new `context["phase"] ==
  "mid_cast"` value, merged into the same `"polling_step_cast"` `Decision`
  (mirrors `engine/action.py::_ask_stealth_or_decrease`'s own
  two-hooks-into-one-offer precedent); a `"mid_cast"` option's own
  `apply(state)` returns the canceled `VoteSource.source_id` instead of
  `None`. `_apply_retroactive_vote_cancellation` removes that source from
  `remaining` (if not yet cast) and its own entry from the `casts` log
  (if already cast), subtracting its votes from whichever direction it
  was cast in. The loop's former "end immediately once `remaining` is
  empty" shortcut was removed (no longer correct once a cancellation
  opportunity can exist with nothing left to cast) — a pure optimization,
  so no existing decision sequence changes. Scalpel Tongue's own card
  module (`cards/scalpel_tongue.py`, `Status.IMPLEMENTED`) was written in
  a later pass.

## OQ-38: Voter Captivation/Scalpel Tongue - who may play it (status: resolved)

- Situation: both cards are typed (at least partly) Action Modifier. Their
  earlier implementations (`cards/voter_captivation.py`,
  `cards/scalpel_tongue.py`'s basic/superior clauses) offered the play to
  *any* ready (Scalpel Tongue: ready and unlocked) vampire either
  Methuselah controls, independent of who is the political action's own
  acting/caller vampire. `rules-auditor` flagged this as a candidate rules
  violation, not a verified-safe implementer's choice: it contradicted this
  project's own Perfect Paragon precedent (OQ-30/31), where the
  structurally identical "[pre] This vampire gets +3 votes" immediately
  after a trigger clause was read as caller-only.
- Rules/interactions: Rulebook §2 Card Types (`data/sources/rulebook/
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
  (necessarily already-locked, Rulebook SS4) `locked` state correctly
  ignored for that check, unlike the non-caller Reaction-rule check.
  `cards/voter_captivation.py::_caller_vampire`,
  `cards/scalpel_tongue.py::_caller_may_play_basic`/`_caller_may_play_
  superior` implement this. Both cards stay `Status.IMPLEMENTED`.

## OQ-39: Loup - implemented despite a ruling gap (status: resolved)

- Situation: Loup's on-file ruling says "Can be used even if the stealth
  is not currently needed" [LSJ 20011214-2], but `cards/loup.py`'s own
  `STEALTH_MODIFIER_HOOK` provider could only ever be offered from inside
  `_duel_stealth_intercept`'s reactive "only when needed" ping-pong
  (`engine/action.py`) — so Loup could not be played against an
  unblockable action, or when no block is attempted at all, contrary to
  that ruling. The module shipped `Status.IMPLEMENTED` with the gap noted
  only in prose/a test name.
- Rules/interactions: krcg's on-file ruling for Loup (as above); this
  project's own OQ-30/31 precedent, where an identical shape (Perfect
  Paragon family needing to add a modifier outside the reactive-only
  window) was resolved by building a new proactive engine primitive
  (`INTERCEPT_DECREASE_HOOK`) rather than guessing around the gap.
- Solution (user-directed, Reading B): a new `STEALTH_INCREASE_HOOK`
  (`engine/action.py`), `INTERCEPT_DECREASE_HOOK`'s sibling for the acting
  side's own stealth -- offered proactively via `hooks.offer_until_pass` at
  the very top of `attempt_block`'s retry loop (alongside the existing
  `INTERCEPT_DECREASE_HOOK` own offer there) and reactively, merged into
  `_duel_stealth_intercept`'s existing union (`_ask_stealth_or_decrease`
  renamed `_ask_stealth_or_modifier`, now a three-way merge). Simpler than
  `ActiveInterceptDecrease`: a stealth increase is never candidate-
  dependent (intercept decrease's own `qualifies(blocker)` predicate exists
  only because intercept is a per-blocker value; stealth is a per-action
  value), so `ActiveStealthIncrease` needs only a `delta`, summed
  unconditionally into `_duel_stealth_intercept`'s `stealth` baseline the
  same way `_active_intercept_decrease` sums into `intercept` -- recomputed
  fresh every call, never cached, same OQ-11 convention. `cards/loup.py`'s
  own provider moved from `STEALTH_MODIFIER_HOOK` to `STEALTH_INCREASE_
  HOOK`, gaining its own per-action `LOUP_STEALTH_GRANTED_KEY` cap in
  `pending` (now reachable from both offer points, unlike the old single
  reactive one) so the standing +1 is activated at most once per action --
  without it, the old reactive-only wiring could in principle have
  restacked the same flat bonus indefinitely within one action (never
  exercised by any registered test, but a latent risk the new cap closes as
  a side effect). Perfect Paragon itself needed no change: its own
  superior clause already uses the (also proactive+reactive) `INTERCEPT_
  DECREASE_HOOK` directly and has no analogous gap. `tests/rules/
  test_stealth_increase.py` proves the mechanism generically (mirroring
  `test_intercept_decrease.py`); `tests/cards/test_loup.py::
  test_can_be_played_proactively_even_when_the_action_is_unblockable`
  proves the fix against the real card.

## OQ-40 - Loup - controller-only or table-wide bonus (status: resolved)

- Situation: `rules-auditor`, reviewing OQ-39's own landing, flagged that
  `cards/loup.py`'s own scope assumption ("Both clauses... bind to the
  *controller's own* Toreador vampires, never the opponent's") carried no
  citation — `_provide_loup`/`_provide_loup_burn` only ever read/burned the
  *acting* player's own `turn_cards`, so a Methuselah's Loup could never
  grant the bonus to, or be burned by, the *other* Methuselah's own
  Toreador vampire. Pre-existing since OQ-34's original pass; OQ-39 only
  made both offer points newly reach this same unexamined assumption.
- Rules/interactions: Loup's own printed text has no "you control" --
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
  already-in-play copy's own activation option, since OQ-40 means they are
  independent, additive opportunities.
