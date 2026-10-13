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

## OQ-9 - Bonding - stealth_modifier omits action type (status: resolved)

- Situation: Bonding (100236)'s superior clause grants "+1 stealth,"
  usable only during a bleed action — but the `"stealth_modifier"`
  hook context carried no field saying which action (bleed vs. hunt)
  was in progress, so a provider could not correctly gate on it.
- Rules/interactions: card text and rulings ([TOM 19951109],
  [LSJ 19980824]/[RTR 19941109]) are explicit and consistent — not a
  ruling ambiguity, a missing engine capability.
- Solution: threaded an `action: str | None` discriminator through
  `perform_minion_action`/`attempt_block`/`_duel_stealth_intercept`
  into the stealth/intercept hook context and the block-attempt
  decision; production call sites pass named constants
  `ACTION_BLEED`/`ACTION_HUNT`/`ACTION_POLITICAL` (added so a future
  typo can't silently fail to match a provider's own check). Card
  itself stays `blocked` (see OQ-11 for the remaining gap).

## OQ-10 - Contested unique allies lack hidden state (status: resolved)

- Situation: `AllyView`/`build_observation` showed every in-play ally
  unconditionally to both players — correct for a non-unique ally but
  not for a contested unique one.
- Rules/interactions: Rulebook §4 Advanced Rules > Contested Cards is
  one unified mechanism for every unique card, crypt or not (face
  down, out of play, 1 pool/unlock-phase or yield); the 2P variant's
  "stays in play, usable" override is scoped to crypt cards only (by
  its own title and aside) — so a contested ally follows the
  unmodified rulebook rule. A recruited ally is itself played face up,
  so unlike an uncontrolled vampire a contested ally's identity is
  never actually secret — no anonymization branch is needed, only a
  zone/usability marker.
- Solution: added `AllyInPlay.contested_with` and a `"contested"` zone
  value; `engine/allies.py::detect_contest_on_recruit` (mirrors the
  vampire-side function), wired into `_perform_recruit_ally`;
  `AllyView.contested: bool`. A pool sweep found six more unique
  allies plus one unique Equipment (Shilmulo Tarot) sharing this gap.
  The resolution loop itself (pay/yield) was deliberately left to
  OQ-15; Equipment-side tracking is left open (no card needs it yet).

## OQ-11 - Bonding - carrying an early hook effect forward (status: resolved)

- Situation: Bonding's superior clause must produce two effects from
  one play — "+1 stealth" (usable only in the earlier block-attempt
  window) and "+1 bleed" (only readable by the later bleed-amount
  window) — and nothing in the engine let one hook application leave
  something for a later one to pick up within the same action.
- Rules/interactions: not a ruling ambiguity (OQ-9 already settled the
  action-type gating); a missing engine primitive. Applying the bleed
  bonus immediately instead (bypassing the later clamp) was rejected:
  it desynchronizes from the amount-window's floor-at-0 clamp and
  Edge-holder check, overcharging the defender in a worked example.
- Solution: `perform_minion_action` now builds a shared, mutable
  `pending: dict` before `attempt_block` runs, threaded into both the
  stealth/intercept hook context and the later bleed-amount-modifier
  context; `_perform_bleed` folds `pending[PENDING_BLEED_AMOUNT_KEY]`
  into the base amount before the clamp. Bonding was then implemented
  against both providers; a related cross-card "(limited)" bookkeeping
  gap (Threats vs. Bonding's superior clause) was fixed by re-keying
  `bleed_bookkeeping` off `pending` instead of the later-window-only
  `amount_box`. `Status.IMPLEMENTED`.

## OQ-12 - 47th Street Royals - recruit-ally action not wired (status: resolved)

- Situation: OQ-7 built the ally representation, but no minion action
  let a player actually recruit one in a real game —
  `_choose_and_perform_action` only ever offered bleed/hunt.
- Rules/interactions: Rulebook §4 "Recruit Ally": any ready minion,
  cost as listed on the card, undirected, +1 stealth; a played card is
  set aside (not yet ash-heaped) until the action resolves, burned
  only on a block (cost not paid).
- Solution: added a "recruit ally" minion action generalizing
  `perform_minion_action` with an `on_blocked` callback (fires instead
  of `resolve` on a block, after combat), `RecruitAllySpec` as the
  hook-option contract, and `play_from_hand_pending` (card leaves hand
  immediately but isn't ash-heaped until the action resolves). Folded
  into the same top-level action-choice decision as bleed/hunt. 47th
  Street Royals' own card module stays `blocked` (its own provider is
  a follow-up); deliberately not extended to allies-as-actor (no card
  needs it, and allies aren't unlocked by the engine yet).

## OQ-13 - 47th Street Royals - recruit_ally_play omits acting vampire (status: resolved)

- Situation: a card's clan requirement (47th Street Royals requires
  Brujah) binds to the specific minion playing it, not merely "the
  Methuselah controls some vampire of that clan" — but the
  `"recruit_ally_play"` hook's context carried no identifier for which
  of possibly several ready-unlocked vampires was acting.
- Rules/interactions: Rulebook §2 "Requirements for Playing Cards"
  draws the minion-card vs. master-card distinction explicitly; a
  minion card (which Ally cards are) binds to the acting minion
  itself.
- Solution: `_choose_and_perform_action` now also passes
  `vampire=vampire.instance_id` into the hook's offer context, letting
  a provider look up the specific acting vampire and check its clan.
  Card module itself stays `blocked` for a future pass.

## OQ-14 - 47th Street Royals - recruit makes contested-ally gap live (status: resolved)

- Situation: with OQ-12/OQ-13 resolved, two independently-built
  2P-legal decks could both recruit their own copy of 47th Street
  Royals — making OQ-10's then-still-open uniqueness gap reachable in
  an ordinary game, not merely latent.
- Rules/interactions: same Contested Cards rule as OQ-10; shipping
  as-is would have silently created two independent, fully-visible
  `AllyInPlay` instances under two controllers instead of the
  mandated face-down/out-of-play treatment.
- Solution: resolved by OQ-10's own fix landing (contest detection on
  recruit). The remaining piece — actually *resolving* a contest once
  created (pay/yield) — was deliberately left to OQ-15. Card stays
  `blocked`.

## OQ-15 - Ally contest resolution loop not wired (status: resolved)

- Situation: OQ-10 added contest *detection* for allies but nothing
  let either player ever pay-or-yield to end one — once a contest
  began, it never ended.
- Rules/interactions: Rulebook §4 Advanced Rules > Contested Cards
  gives one unified pay-1-pool-per-unlock-phase-or-yield mechanism for
  every unique card; the 2P variant's crypt-card override does not
  change this cost/resolution half, only the face-down/usable half,
  and only for crypt cards.
- Solution: added `engine/allies.py::resolve_one_ally_contest` (pay
  keeps `zone="contested"`, no 2P "stays usable" exception for
  allies; yield burns the yielding copy, clears the opponent's
  `contested_with` but leaves its `zone` at `"contested"` until that
  opponent's own next unlock phase) and `_unlock_own_allies` to
  perform that delayed restore; extended the unlock phase's
  pending-effect loop to surface `"contest_ally:"` ids. Shilmulo
  Tarot's own (Equipment-side) contest tracking is flagged as a
  separate, still-open gap, out of scope here.

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
