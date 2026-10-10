# Open questions

Rules or card interactions that the official sources do not settle.
Nothing listed here may be implemented by guessing. Format and
procedure: see `.claude/skills/vtes-rules-reference/SKILL.md`.

## OQ-1: Prey/predator wording in a duel   (status: open)

- Situation: with two players, each Methuselah is the other's prey
  and predator (Rulebook §5). Some card texts distinguish prey from
  predator, or refer to "other Methuselahs" in a way written for
  4–5 players.
- Sources read: Rulebook v1.1 §5; 2P variant page (modified
  2025-05-20); 2P updates page (2026-10-03). No dedicated
  clarification found.
- Candidate readings: to be listed per card when encountered.
- Impacted cards: to be listed.

## OQ-2: Interface target   (status: resolved — digital first)

- Decision: digital-first. The engine owns the full game state and
  exposes explicit legal choices; the first implementation target
  is a CLI interface.
- Rationale: the project is built around deterministic state
  tracking, legal-action decision points, and engine-driven play,
  which are natural to a digital interface and easier to validate
  than a physical-table workflow.
- Scope: the physical-table workflow remains out of scope unless a
  concrete requirement appears. The project will proceed with
  digital play and CLI-first tooling by default.

## OQ-3: Combat "press" step — exact turn order   (status: resolved)

- Situation: Rulebook SS4 Combat describes each round ending with a "press"
  step ("alternating") before the round either ends or another begins. The
  `vtes-rules-reference` skill's condensed mapping names the step and that
  it alternates, but did not spell out which combatant is consulted first.
- Resolution: `rules-auditor` fetched the primary rulebook page directly and
  quoted it verbatim: "The acting minion always gets first opportunity to
  use cards or effects before the opposing minion" — stated as applying at
  every stage of combat, including press. This matches the project's own
  impulse invariant (CLAUDE.md SS5 / Rulebook SS2 Sequencing): the acting
  minion's controller is always asked to press first, every round, never
  alternating by round parity.
- Fix applied: `src/vtesbot/engine/combat.py` (`run_combat`, press step) now
  always orders `[(acting_player, acting_vampire), (blocking_player,
  blocking_vampire)]`, with no round-parity alternation.

## OQ-4: 2P contested crypt cards — exact contest trigger moment   (status: resolved)

- Situation: the 2P variant's contested-crypt-card rule (per the
  `vtes-rules-reference` skill's condensed mapping) gave the *resolution*
  cost (1 pool per unlock phase, or yield/burn) but the mapping did not
  state the precise moment a contest begins.
- Resolution: `rules-auditor` fetched the primary 2P variant page directly
  (<https://www.vekn.net/two-player-format/655-two-player-variant-for-vampire-the-eternal-struggle>)
  and quoted it verbatim: "If more than one unique crypt card with the same
  name is brought into play, that means control of the card is being
  contested" / "A second copy brought in later is immediately contested,
  and can still be used as normal." This confirms the implemented reading
  (contest triggers on reveal into play, not while both copies are merely
  face down/uncontrolled) is correct.
- Code: `src/vtesbot/engine/contests.py` (`detect_contest_on_reveal`) — no
  change needed, reading A was already implemented.

## OQ-5: Does a failed block attempt lock the blocker?   (status: resolved)

- Situation: `src/vtesbot/engine/action.py::attempt_block` locks the
  blocking vampire only when the block *succeeds* (intercept >= stealth,
  leading to combat), not when an attempt is made but fails to connect
  (stealth exceeds intercept).
- Resolution: confirmed by `rules-auditor` on a follow-up pass, re-fetching
  the rulebook's "Resolve the Action" step verbatim: "If the action is
  blocked, then any card played to perform the action is burned and the
  block is resolved with these two simultaneous consequences: the blocking
  minion is locked and enters combat with the acting minion... The effects
  of the action do not take place when the action is blocked." Locking is
  stated as a consequence tied strictly to the action *being blocked*, i.e.
  a successful block — combined with "If one attempt to block fails,
  another can be made as often as the blocking Methuselah wishes" (a locked
  minion could not retry), this confirms reading A (implemented) over
  reading B.
- No code change needed: `attempt_block` already implements reading A
  correctly.
- Impacted code: `src/vtesbot/engine/action.py` (`attempt_block`).

## OQ-6: Referendum vote-tally/pass-fail for two Methuselahs (status: resolved)

- Situation: the `vtes-rules-reference` skill's condensed mapping of
  Rulebook §4 Politics gives *where votes come from* ("1 from a political
  action card (max 1 per Methuselah), titles (primogen 1, prince/baron 2,
  justicar 3, Inner Circle 4; Sabbat and other sects per §6–7), burning the
  Edge = 1. Only ready minions vote. Ties fail.") and *when terms are
  chosen* ("Terms chosen only after success"), but does not state what a
  referendum's cast votes are compared against to decide pass/fail, nor what
  "ties fail" is relative to. This pool's own three Political Action cards
  additionally surfaced a related, unexplained state: card rulings for
  Perfect Paragon and Scalpel Tongue both read "[c]annot be used during a
  referendum that is automatically passing" [PIB 20150105] [LSJ 19980107],
  raising the question of whether that's a duel-specific mechanic (only one
  possible opposing voter).
- Resolution: `rules-auditor` re-fetched both primary sources directly
  (<https://www.vekn.net/rulebook/4-detailed-turn-sequence>, Politics/
  Referendum subsection, and the 2P variant page) and settled all three
  bundled questions:
  1. **What are votes compared against, what does "ties fail" mean?**
     Quoted verbatim: "all Methuselahs may now cast any votes and ballots
     they have... in any order... there is no obligation to cast"; "Each
     vote or ballot cast is cast either 'for' or 'against' the referendum";
     "If there are more votes for the referendum than against, it passes...
     Otherwise, the referendum fails... Tied referendums fail." Votes are a
     straight for/against tally across whatever sources each Methuselah
     chooses to use (political-action card, titled ready vampires,
     burning the Edge, other cards — "Methuselahs have no inherent votes or
     ballots") — not "Methuselah vs Methuselah". This degrades cleanly to
     two players: an uncontested referendum is simply 0-for/0-against,
     which ties, which fails, same as with any player count. **Reading A
     confirmed.**
  2. **Does the 2P variant override this?** No — re-fetched directly;
     confirmed no referendum-procedure override exists, only the
     already-known title-contest exception.
  3. **Is "automatically passing" a duel-specific mechanic?** No —
     **reading B was wrong.** The actual General Ruling [PIB 20150105],
     fetched from the forum post krcg cites
     (<https://www.vekn.net/forum/rules-questions/68465-voting-is-complicated#68493>):
     "If a referendum will pass automatically (e.g., Cryptic Rider,
     Charming Lobby, Malkavian Rider Clause, Día de los Muertos), then no
     casting votes or ballots occurs during the automatic referendum." This
     is a card-text-triggered category (specific cards whose own printed
     text declares their called referendum passes automatically), entirely
     unrelated to player count. Confirmed via krcg that none of this
     pool's three Political Action cards (Disputed Territory, Kine
     Resources Contested, Parity Shift) carry this text themselves, so the
     mechanic does not apply to any card in the current pool.
- Remaining work is engineering, not a ruling: `political_action` should
  gain a real polling step (enumerate each Methuselah's available vote
  sources, let each commit for/against, tally, apply ties-fail) to replace
  the current `UnresolvedRulingError("OQ-6")`; once built, the cards below
  can move from `blocked` to implementation.
- Note for later: if a card entering the 2P pool ever prints its own
  "this referendum passes automatically" text (none currently do), that
  card's own text is authoritative per the Golden Rule for Cards (CLAUDE.md
  §2) and needs no new Open Question — it's a plain card-text clause, not
  an unsettled ruling.
- Impacted code: `src/vtesbot/engine/politics.py::political_action` raises
  `UnresolvedRulingError("OQ-6")` immediately once a political action goes
  unblocked, rather than guessing. Impacted cards (all registered `blocked`,
  reason `OQ-6`): Disputed Territory, Kine Resources Contested, Parity Shift
  (call a referendum); Perfect Paragon, Scalpel Tongue, Voter Captivation,
  Oxford University, England (only usable during/after a referendum's
  polling step or resolution); crypt-vampire printed abilities Alexa
  Draper, Diana Iadanza, Fiorenza Savona, Marcos Belegrad, Modius, Queen
  Anne (each reads or modifies a referendum's polling step or who called
  it).

## OQ-7: No ally-in-play entity -- 47th St. Royals (102217) (status: resolved)

- Situation: card text (verbatim, via krcg, 2026-10-09): "Unique mortal with
  2 life. 1 strength, 0 bleed. You can burn 47th Street Royals to reduce a
  bleed against you by 3." Card type `Ally`, clan requirement Brujah, no
  discipline requirement, `cost is None`, `burn_option is False` (per krcg's
  own fields -- the burn mechanic here is the card's own printed text, not
  the engine's generic "burn_option" flag). This is not a ruling ambiguity:
  the text is plain. The block is a missing engine representation.
- Missing mechanism: `src/vtesbot/engine/state.py`'s `PlayerState` has no
  notion of an ally (or retainer) in play at all -- only `vampires: dict[str,
  VampireInPlay]`. An Ally is a distinct minion-like entity with its own life
  total, strength and bleed values, that can be brought into play (for a
  pool/blood cost, paid as an action — out of milestone-2's scope, which only
  implements the bleed/hunt default minion actions), can act (bleed/block/
  fight) independently of any vampire, and can be destroyed (loses all its
  life) or burned by its controller's own card text (this card's reaction).
  `src/vtesbot/cards/registry.py`'s `Hook.ALLY_ENTITY` is named for
  classification only, with no engine wiring (no call site in `engine/`
  offers it, no `AllyInPlay`-equivalent dataclass exists) -- confirmed by
  grep across `src/vtesbot/engine/`.
- What would be needed: an `AllyInPlay` dataclass (life, strength, bleed,
  controller, zone/locked analogous to `VampireInPlay`) on `PlayerState`, a
  way to play an Ally library card into that zone (cost, timing window), and
  at least the one new reaction window this specific card needs (a burn-to-
  reduce-bleed reaction analogous to Telepathic Counter's
  `"bleed_amount_modifier"` hook, but consuming the ally itself as its cost
  instead of a card from hand). This is `rules-engineer` scope, not a card
  module.
- Impacted code (at the time this was opened): none yet (no `AllyInPlay`
  representation existed to extend). Impacted cards: 47th Street Royals
  (registered `blocked`, reason `OQ-7`).
- Resolution (`rules-engineer` pass): added `AllyInPlay` (`src/vtesbot/
  engine/state.py`: `instance_id`, `krcg_id`, `name`, `controller`, `life`,
  `strength`, `bleed`, `zone`, `locked`, `is_ready_unlocked`) and
  `PlayerState.allies: dict[str, AllyInPlay]` / `PlayerState.
  new_ally_instance_id()` (own `"<player>-A<n>"` namespace, distinct from
  vampires' `"<player>-V<n>"`). `src/vtesbot/engine/allies.py` adds
  `recruit_ally(state, player, *, krcg_id, name, life, strength=0, bleed=0)`
  (creates the ally ready-but-locked, per "recruited ally cannot act this
  turn") and `burn_ally(state, player, ally)` (mirrors `engine/damage.py::
  burn_vampire`'s zone/locked reset). 47th Street Royals' own reaction needs
  no new hook wiring: it registers against the already-wired
  `"bleed_amount_modifier"` hook exactly like `telepathic_counter.py`, with
  `burn_ally` as the cost instead of playing a card from hand -- proven by a
  scaffolding scenario test using a fake provider
  (`tests/rules/test_allies.py::test_ally_burned_as_a_bleed_reduction_
  reaction_cost`).
  Deliberately **not** built (no card in the pool needs it, CLAUDE.md rule
  2): the full "recruit ally" minion action (its own announce/block-attempt
  window, mirroring `engine/action.py::perform_minion_action`) and ally
  bleed/block/combat participation. `recruit_ally` is the minimal "bring
  into play" effect such a future action's `resolve()` could call once
  built; until then, and for 47th Street Royals (which never acts, blocks,
  or fights), it is also the direct entry point a card module or scenario
  test uses.
- Follow-up (`rules-auditor` finding, same pass): the initial `AllyInPlay`
  landing gave an ally no representation in `engine/observation.py` at all
  -- an ally recruited via `recruit_ally` was invisible to *both* players'
  `Observation`, even though Rulebook SS4 Recruit Ally makes a ready-region
  ally fully public, exactly like a ready vampire (there is no face-down
  state for an ally to be in: `AllyInPlay`'s only zones are `"ready"`/
  `"burned"`, never `"uncontrolled"`). Fixed by adding `AllyView`
  (`engine/observation.py`, mirroring `VampireView`'s shape minus the
  conditional `visible_identity` branch, since an ally has nothing to hide)
  and `Observation.allies: tuple[AllyView, ...]`, populated in
  `build_observation` from both players' `PlayerState.allies` unconditionally
  (not gated on `viewer`/`controller`, unlike the uncontrolled-vampire case).
  Exported via `src/vtesbot/engine/__init__.py`. Proven by
  `tests/rules/test_observation.py::
  test_a_recruited_ally_is_fully_visible_to_the_other_player` and
  `test_both_players_allies_appear_in_each_others_observation`.
- Impacted code: `src/vtesbot/engine/state.py`, `src/vtesbot/engine/
  allies.py` (new), `src/vtesbot/engine/observation.py`, `src/vtesbot/
  engine/__init__.py` (exports). Card registration is unchanged (47th
  Street Royals stays `blocked`/`OQ-7` in the registry; re-implementing it
  against this capability is `card-implementer`'s job).

## OQ-8: Attachment effects unconsulted -- Celerity (100312) (status: resolved)

- Situation: card text (verbatim, via krcg, 2026-10-09): "Discipline. Put
  this card on a vampire. This vampire gets +1 level of Celerity [cel] and
  +1 capacity. Cannot be put on a vampire with superior Celerity [CEL]."
  Card type `Master`, no discipline/clan requirement, `cost is None`,
  `trifle is False`. Not a ruling ambiguity -- the text is plain and this is
  the generic "Discipline"-type master card pattern (one per discipline).
  The block is a missing engine representation.
- The "put this card on a vampire" part has an existing representation:
  `src/vtesbot/engine/state.py::VampireInPlay.attachments: list[CardAttachment]`
  (`engine/cards.py::CardAttachment`) already models "a card physically
  attached to a vampire," and its docstring literally names Celerity as the
  motivating example. Playing it as a master-phase action is also already
  wired generically (`"master_phase_play"` hook, `engine/phases/master.py`,
  used by Life in the City). So *attaching* the card is not blocked.
- What is blocked: the card's two numeric effects ("+1 level of Celerity",
  "+1 capacity") have no consumer anywhere in the engine. `vampire.card` is
  a frozen `CryptCard` documented as "deck-construction identity only"
  (`engine/cards.py`); every place that reads a vampire's capacity reads
  `vampire.card.capacity` directly with no attachment-aware indirection:
  `engine/damage.py::add_blood` (`added = min(amount, vampire.card.capacity -
  vampire.blood)`) and `engine/phases/influence.py` (two call sites, `v.blood
  < v.card.capacity` / `v.blood >= v.card.capacity`). Likewise, every
  discipline-level check so far reads `vampire.card.disciplines` directly
  (e.g. `src/vtesbot/cards/threats.py`, `telepathic_counter.py`). None of
  these consult `VampireInPlay.attachments`. `Hook.EQUIPMENT_ATTACHMENT`
  (`registry.py`) is, per its own comment, "named for classification; no
  engine wiring exists yet." Implementing Celerity today would mean either
  (a) a no-op attachment whose printed effect is silently dropped (CLAUDE.md:
  "never mis-resolves a card"), or (b) mutating the frozen `vampire.card`
  identity object in the card module to fake the bonus -- a workaround
  routing around a missing engine mechanism, which CLAUDE.md explicitly
  forbids ("Do not hack around it inside the card module").
- What would be needed: an engine-exposed "effective capacity" / "effective
  discipline levels" computation for a `VampireInPlay` that folds in its
  `attachments` (e.g. a `VampireInPlay.effective_capacity` /
  `effective_disciplines` property, or a wired `"equipment_attachment"`-style
  hook), with `engine/damage.py::add_blood`, both `engine/phases/
  influence.py` capacity checks, and any discipline-level-gated card updated
  to consult it instead of `vampire.card.*` directly. This is
  `rules-engineer` scope (it touches `engine/` files, not just `cards/`).
- Impacted code (at the time this was opened): `src/vtesbot/engine/
  damage.py`, `src/vtesbot/engine/phases/influence.py`, `src/vtesbot/
  engine/state.py`. Impacted cards: Celerity (registered `blocked`, reason
  `OQ-8`); any future discipline/archetype-granting master card (Potence,
  Obfuscate, etc.) and any future card whose legality depends on an
  attached discipline level would hit the same gap.
- Resolution (`rules-engineer` pass): added `src/vtesbot/engine/
  attachments.py`, exposing `effective_capacity(state, vampire)` and
  `effective_disciplines(state, vampire)` -- `vampire.card.capacity`/
  `.disciplines` (the frozen, deck-construction-identity `CryptCard`, left
  untouched per its own docstring) folded with whatever any attached card's
  own module contributes via two new passive hooks,
  `"capacity_modifier"` (`hooks.sum_modifiers` contract: numeric, e.g.
  Celerity's "+1 capacity") and `"discipline_level_modifier"` (a new
  `hooks.union_modifiers` helper added alongside `sum_modifiers`: set-valued,
  e.g. Celerity's "+1 level of Celerity [cel]"). Both are mandatory/passive
  (CLAUDE.md rule 3's "mandatory effects" exception -- an attachment's bonus
  is not something its controller chooses to apply turn to turn), so no
  `Decision` is raised for them; a card module recognizes its own `krcg_id`
  among `vampire.attachments` and contributes the bonus, same pattern as
  every other hook.
  Updated every `engine/` call site OQ-8 named to stop reading
  `vampire.card.capacity` directly: `engine/damage.py::add_blood` (now
  `add_blood(state, vampire, amount)` -- the signature gained a leading
  `state` parameter; its one existing caller outside `engine/`,
  `src/vtesbot/cards/life_in_the_city.py`, was updated to match, a
  mechanical call-site fix, not new card behaviour), both capacity checks
  in `engine/phases/influence.py`, and `engine/observation.py`'s
  `VampireView.capacity` (so a revealed vampire's capacity shown to either
  player already reflects any attachment, since an attached card on a
  ready/torpor vampire is public information). Proven by
  `tests/rules/test_attachments.py` using fake attachment-bonus providers
  (not a real card).
  **Not** touched, per this task's explicit scope: `src/vtesbot/cards/
  threats.py` and `telepathic_counter.py` still read `vampire.card.
  disciplines` directly rather than `effective_disciplines(state, vampire)`
  -- both are already-`implemented` cards, and updating a `cards/*.py`
  module is `card-implementer`'s job, not this pass's. They have the same
  latent gap OQ-8 originally described (an attached discipline-granting
  card would not be seen by either card's own discipline check); switching
  them over is flagged here for a future `card-implementer`/`rules-auditor`
  pass rather than guessed at silently.
- Follow-up (`rules-auditor` findings, same pass): two small corrections,
  neither changing the resolution above.
  1. `src/vtesbot/cards/registry.py`'s `Hook` enum had not been updated to
     list `"capacity_modifier"`/`"discipline_level_modifier"` as wired (they
     were simply missing, rather than miscategorized); added
     `Hook.CAPACITY_MODIFIER`/`Hook.DISCIPLINE_LEVEL_MODIFIER` to the "wired
     this pass" group with matching string values, and fixed
     `src/vtesbot/cards/celerity.py`'s registration, which cited the
     unrelated, still-unwired `Hook.EQUIPMENT_ATTACHMENT`, to cite these two
     instead (they are what will actually back Celerity's two numeric
     effects once implemented).
  2. `hooks.union_modifiers` (and `effective_disciplines`, which wraps it)
     returned a `frozenset[str]`, a latent determinism footgun (CLAUDE.md
     SS5: "same seed + same decisions => same game") -- Python's string
     hashing is randomized per process, so a future card module iterating
     this set to build `Decision.choices` would get non-reproducible
     ordering across process runs from the same replay log. Both now return
     a sorted `tuple[str, ...]` instead; no current consumer needed set
     semantics. `tests/rules/test_hooks.py::
     test_union_modifiers_returns_a_sorted_tuple_not_a_frozenset` and the
     two `tests/rules/test_attachments.py` tests asserting
     `effective_disciplines`'s return value were updated to match.
- Impacted code: `src/vtesbot/engine/attachments.py` (new),
  `src/vtesbot/engine/hooks.py` (`union_modifiers`), `src/vtesbot/engine/
  damage.py`, `src/vtesbot/engine/phases/influence.py`, `src/vtesbot/
  engine/observation.py`, `src/vtesbot/engine/__init__.py` (exports),
  `src/vtesbot/cards/life_in_the_city.py` (mechanical `add_blood` call-site
  update only), `src/vtesbot/cards/registry.py`, `src/vtesbot/cards/
  celerity.py` (hook-tag fix only). Card registration is unchanged (Celerity
  stays `blocked`/`OQ-8` in the registry; re-implementing it against this
  capability is `card-implementer`'s job).

## OQ-9: stealth_modifier omits action type -- Bonding (status: resolved)

- Situation: card text (verbatim, via krcg, 2026-10-09): "Only usable during
  a bleed action. [dom] +1 bleed (limited). [DOM] +1 stealth and +1 bleed
  (limited)." Rulings (verbatim): "[DOM] Cannot be used if you do not need
  the stealth at the time you play it." [TOM 19951109]; "[DOM] Cannot be
  used to increase the stealth of a non-bleed action." [LSJ 19980824] [RTR
  19941109]. Not a ruling ambiguity -- both the printed restriction and the
  ruling are explicit and consistent. The block is a missing engine
  capability.
- The basic-level clause ("[dom] +1 bleed (limited)") is clean and would be
  implementable exactly like `src/vtesbot/cards/threats.py` (same
  `"bleed_amount_modifier"` hook, only ever offered from `_perform_bleed`,
  so "only usable during a bleed action" is automatically satisfied for that
  clause with no extra check).
- What is blocked: the superior-level clause additionally grants "+1
  stealth," which must go through the already-wired `"stealth_modifier"`
  hook (`engine/action.py::_duel_stealth_intercept`) to have any actual
  effect on whether a block attempt succeeds (the `"bleed_amount_modifier"`
  window only opens *after* the bleed is already unblocked, per
  `telepathic_counter.py`'s own documented timing note, so applying "+1
  stealth" there would be too late to matter -- not a legal substitute).
  However, `_duel_stealth_intercept` is called identically by both
  `engine/phases/minion.py::_perform_bleed` and `_perform_hunt` (both route
  through `engine/action.py::perform_minion_action`), and the context dict
  it builds (`actor`, `defender`, `acting_vampire`, `blocking_vampire`,
  `stealth`, `intercept`) carries no field saying which action (bleed vs.
  hunt) is currently being attempted. A provider registered against
  `"stealth_modifier"` therefore cannot tell whether "Only usable during a
  bleed action" / "[DOM] Cannot be used to increase the stealth of a
  non-bleed action" is satisfied. The only available proxy -- the numeric
  `base_stealth` the window started from (0 for bleed, 1 for hunt, per
  `engine/phases/minion.py`'s `BLEED_STEALTH`/`HUNT_STEALTH` constants) --
  is an implementation-detail coincidence, not sourced from the card text or
  a ruling, and would break silently if any other stealth-modifying card
  ever changed a hunt's stealth before Bonding is offered, or if those
  constants changed; relying on it would be exactly the "no guessing" the
  project forbids.
- Because the card's superior clause cannot be correctly gated, and the
  registry/CLAUDE.md model a card as either fully `implemented` (all of its
  text, with basic/superior tested separately) or `blocked` -- not a partial
  implementation of only the clean clause -- the whole card is blocked
  pending the fix below.
- What would be needed: thread an action-type discriminator (e.g. `action:
  Literal["bleed", "hunt"]`, or equivalently the resolved action's own
  identity) through `engine/action.py::perform_minion_action` /
  `attempt_block` / `_duel_stealth_intercept` into the context passed to
  `hooks.offer(STEALTH_MODIFIER_HOOK, ...)` (and, for symmetry/future cards,
  probably `INTERCEPT_MODIFIER_HOOK` too). This is `rules-engineer` scope
  (it touches `engine/action.py` and its callers in `engine/phases/
  minion.py`).
- Impacted code (at the time this was opened): `src/vtesbot/engine/
  action.py`, `src/vtesbot/engine/phases/minion.py`. Impacted cards: Bonding
  (registered `blocked`, reason `OQ-9`).
- Resolution (`rules-engineer` pass): `engine/action.py::perform_minion_
  action`, `attempt_block` and `_duel_stealth_intercept` all gained an
  `action: str | None = None` parameter, forwarded unchanged into the
  `"stealth_modifier"`/`"intercept_modifier"` hook context (`context
  ["action"]`) and into the `"block_attempt"` decision's own context. Used a
  plain `str | None` rather than a closed `Literal["bleed", "hunt"]`:
  `engine/politics.py::political_action` already calls `attempt_block`
  directly for a third action kind (`"political_action"`), and a closed
  Literal would need editing again for every future default minion action
  (equip, leave torpor, etc.) -- an open string name avoids re-touching
  `engine/action.py` for that reason alone, while still giving a provider
  something concrete to check instead of guessing from `base_stealth`'s
  numeric value. Production call sites updated: `engine/phases/minion.py::
  _perform_bleed` passes `action="bleed"`, `_perform_hunt` passes
  `action="hunt"`, `engine/politics.py::political_action` passes
  `action="political_action"`. Existing callers that do not pass `action`
  (all pre-existing tests) default to `None` -- a zero-regression change
  (confirmed: all 113 previously-passing tests still pass unmodified).
  Proven end-to-end (production call sites, not just the lower-level
  helpers) by `tests/rules/test_action_discriminator.py`, including a fake
  "only during a bleed" provider (stand-in for Bonding's superior clause)
  that fires for a bleed and is silent for a hunt.
- Follow-up (`rules-auditor` finding, same pass): the three producing call
  sites (`engine/phases/minion.py`'s two, `engine/politics.py`'s one) passed
  bare string literals (`"bleed"`, `"hunt"`, `"political_action"`) into
  `action=...` -- a future typo (e.g. `"Bleed"`) would not raise, it would
  just silently fail to match a hook provider's own `context.get("action")
  == ...` check, exactly the "never mis-resolves a card" risk CLAUDE.md
  warns against. Fixed by adding named, open-string constants
  `ACTION_BLEED = "bleed"`, `ACTION_HUNT = "hunt"`,
  `ACTION_POLITICAL = "political_action"` to `engine/action.py` itself (kept
  as plain module-level `str` constants, not a closed `Literal` or a new
  `StrEnum`, for the same "more default actions are coming" reason the
  parameter type stayed an open `str | None`); the three call sites, and the
  `Choice`/comparison in `engine/phases/minion.py::
  _choose_and_perform_action`, now import and use them instead of
  re-typing the strings. Any future hook provider gating on a specific
  action should import and compare against these constants too, rather than
  hard-coding its own copy. Zero-regression (same 135 tests pass).
- Impacted code: `src/vtesbot/engine/action.py`,
  `src/vtesbot/engine/phases/minion.py`, `src/vtesbot/engine/politics.py`.
  Card registration is unchanged (Bonding stays `blocked`/`OQ-9` in the
  registry; re-implementing it against this capability is
  `card-implementer`'s job).

## OQ-10: Contested unique allies lack hidden state (status: resolved)

- Situation: found by `rules-auditor` while re-reviewing OQ-7's ally
  Observation fix. `AllyView`/`build_observation`
  (`src/vtesbot/engine/observation.py`) show every in-play ally
  unconditionally to both players, on the premise that an ally has no
  face-down state. That premise is correct for a *non-unique* ally, but not
  in general. Not a ruling ambiguity -- the text is plain. The block is a
  missing engine representation, same category as OQ-7/8/9.
- Sources: Rulebook SS4 ("ADVANCED RULES > Contested Cards", live-fetched
  and cross-checked against the local cache
  `data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md`): "Some of
  the cards in the game represent unique resources, such as specific
  locations, equipment, or people. These cards will be identified as
  'unique' in their card text... If more than one unique card with the same
  name is brought into play, that means control of the card is being
  contested. For the duration of the contest, all of the contested cards
  are turned face down and are out of play." The 2P variant's
  contested-crypt-card override (stay in play, usable, 1 pool/unlock phase
  or yield) is scoped to crypt cards only -- re-checked live, the variant
  page's own section is titled "Contested crypt cards" and never mentions
  allies, equipment or locations. So a contested *unique* ally follows the
  unmodified rulebook rule: face down, out of play, for both copies, for
  the contest's duration.
- What's missing: `AllyInPlay` (`engine/state.py`) has no `contested_with`
  field (unlike `VampireInPlay`, which has one, consumed by
  `engine/contests.py::detect_contest_on_reveal`/`resolve_one_contest`);
  `recruit_ally` (`engine/allies.py`) never checks for an opposing
  same-name unique ally already in play; `AllyView`/`build_observation`
  have no branch to hide a contested ally's identity.
- Why this is open, not yet fixed: practical impact today is zero -- no
  code path can create two controllers' copies of the same unique ally (no
  "recruit ally" minion action exists yet, and the only unique-ally card in
  the pool, 47th Street Royals, is still `blocked`/OQ-7). This is a latent
  gap flagged before it becomes live, not an active information leak.
- What would be needed: extend `AllyInPlay` with contest tracking mirroring
  `VampireInPlay.contested_with`/`engine/contests.py`, and give
  `AllyView`/`build_observation` a hidden/anonymized branch for a contested
  ally, analogous to how an opponent's face-down uncontrolled vampire is
  anonymized today. `rules-engineer` scope.
- Also worth a quick sweep (not done yet): whether any other card in the 2P
  allowed list is a unique Ally, Equipment, or Location -- the same gap
  would apply to any of them, not just 47th Street Royals.
- Impacted code: `src/vtesbot/engine/observation.py` (`AllyView`,
  `build_observation`), `src/vtesbot/engine/state.py` (`AllyInPlay`),
  `src/vtesbot/engine/allies.py` (`recruit_ally`). Impacted cards: 47th
  Street Royals (already `blocked`/OQ-7; this is an additional prerequisite
  before unblocking it), and any future unique Ally/Equipment/Location card.
- Status update (`card-implementer`, 2026-10-09, see OQ-14): no longer
  latent -- confirmed live and reachable now that OQ-12 and OQ-13 are both
  resolved (47th Street Royals' own recruit side is otherwise ready to wire).
- Resolution (`rules-engineer` pass, 2026-10-09): re-fetched the full
  Rulebook SS4 "Advanced Rules > Contested Cards" section live (cross-checked
  against the local cache, `data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md`, lines 38-56) and the 2P variant's own
  "Contested crypt cards" section (`data/sources/2p-variant/2026-10-09/
  variant.md`), not just the single sentence this entry originally quoted.
  Two findings refine, but do not reverse, this entry's own framing:
  1. The base rulebook rule is one unified mechanism for *every* unique card
     (crypt or not): "turned face down and are out of play" for the
     contest's duration, resolved by "1 pool, which you pay during each of
     your unlock phases. Instead of paying ... you may choose to yield the
     card ... [burned] ... If all other cards contesting your unique card
     are yielded, then the card is unlocked and turned face up during your
     next unlock phase." The 2P variant's "Contested crypt cards" section
     overrides *only* the face-down/out-of-play half, and only for crypt
     cards -- confirmed by its own title and its own aside, "(Note: this
     means that contested crypt cards are no longer out of play)", which by
     negation leaves the face-down/out-of-play treatment (and the identical
     pay-1-pool-or-yield cost) in force, unmodified, for an Ally/Equipment/
     Location. So the contest-*resolution* mechanism for an ally is **not**
     a genuine ruling ambiguity after all, contrary to what this entry and
     OQ-14 anticipated when they were filed -- it is directly sourced, and
     is the same cost structure `engine/contests.py::resolve_one_contest`
     already applies to crypt cards.
  2. Despite the base rule's "turned face down" wording, a contested ally's
     *identity* is never actually secret from either player: "Recruit Ally"
     is itself played face up at announce time (Rulebook SS4; `engine/
     allies.py::RecruitAllySpec`'s own docstring), so a contest can only
     ever arise the instant a *second* same-named ally is recruited, already
     face up, against a first copy that was itself recruited face up earlier
     -- both identities are mutually known to both players from the moment
     the contest is created. So, unlike `VampireView`'s `visible_identity`
     branch (which hides a genuinely-unrevealed, still-face-down
     *uncontrolled* crypt card), no name/stat-anonymizing branch is sourced
     or needed for `AllyView`; "face down" for an ally is a zone/usability
     marker, not an information-hiding mechanic.
  Built, matching this entry's own "what would be needed" almost exactly:
  `AllyInPlay.contested_with` (`engine/state.py`, mirrors
  `VampireInPlay.contested_with`) and a third `zone` value, `"contested"`
  (alongside `"ready"`/`"burned"`) to represent "out of play" (distinct from
  the crypt-card case, where the 2P override means `zone` never has to
  change); `engine/allies.py::detect_contest_on_recruit` (mirrors
  `engine/contests.py::detect_contest_on_reveal`'s shape: checks only the
  opponent's allies, matches by printed name, flags both sides) -- but,
  unlike the vampire-side function, also moves *both* colliding allies'
  `zone` to `"contested"`, since (per finding 1 above) the ally case is not
  shielded by any 2P "stays usable" override. Wired into the one real
  production call site, `engine/phases/minion.py::_perform_recruit_ally`'s
  own `resolve()`, immediately after `recruit_ally(...)` succeeds -- mirrors
  `engine/phases/influence.py`'s own `detect_contest_on_reveal` call site
  after a vampire's reveal. `AllyView` gained a `contested: bool` field
  (populated from `contested_with is not None`); its docstring and
  `build_observation`'s were corrected to no longer claim an ally has
  nothing to hide unconditionally, while explaining (per finding 2) why no
  anonymization branch is needed even so. Exported via `engine/__init__.py`.
  Proven by `tests/rules/test_ally_contests.py`: two same-named allies, one
  per player, both get `contested_with` set and `zone` moved to
  `"contested"` (both the lower-level `detect_contest_on_recruit` call and,
  separately, the real `_perform_recruit_ally` minion-phase path, the same
  "production call site, not just the lower-level helper" bar OQ-13's own
  resolution set); differently-named allies and a single player's own two
  same-named allies (mirrors `detect_contest_on_reveal`'s identical,
  pre-existing scope boundary -- not a new gap) are confirmed *not* to
  contest; the `Observation` branch is proven both for a contested ally
  (full identity still visible, `zone == "contested"`, `contested is True`)
  and, as a zero-regression check, for an uncontested one (`contested is
  False`, matching every pre-existing ally-visibility test unmodified). Full
  suite green, 185 passing (up from 178; 7 new, 0 regressions), `ruff check`/
  `ruff format --check` clean.
  Also ran the "quick sweep" this entry flagged as not yet done: queried
  every `Library`-type card in the active 2P allowed list
  (`data/formats/2p/2026-10-03.json`, 198 entries) against `krcg.load()`
  for `types` and printed text. 47th Street Royals is not the only unique
  Ally in the pool -- six more are already 2P-legal and unimplemented (seven
  unique allies total):
  Double Deuce (102220), Heartrender (102327), Political Ally (101411),
  Vagabond Mystic (102087), The Vozhd of Juiz de Fora (102364), The Vozhd of
  Sofia (102267) -- plus one unique Equipment, Shilmulo Tarot (101767,
  "Unique."). The fix above is general (keyed on `AllyInPlay`/`AllyView`,
  not this specific card), so all six unique allies are covered by it the
  moment any of them is wired. Shilmulo Tarot (Equipment) is **not**
  covered: equipment lives in `CardAttachment` (`engine/cards.py`), a wholly
  different representation with no `contested_with` tracking of its own --
  that remains an open gap for a future pass, not addressed here (no card
  module needs it yet, same "no guessing ahead of a sourced need" boundary
  this entry itself was opened under).
  Deliberately **not** built, and **not** a ruling ambiguity (see finding 1
  above) -- see OQ-15: the unlock-phase pay-1-pool-or-yield loop that would
  ever let a contested ally's controller actually resolve (end) the
  contest. A contested ally can now be correctly detected and marked out of
  play, but nothing yet offers either player a decision to pay or yield it,
  so once created, a contest never ends in this engine today. Scoped out of
  this pass deliberately (CLAUDE.md "small commits, one rule mechanism per
  change"; this entry's own "Impacted code" list, and the task that reopened
  it, both named `engine/state.py`/`engine/allies.py`/`engine/observation.py`
  specifically, not `engine/phases/unlock.py`) -- tracked, not silently
  dropped, as OQ-15.
- Impacted code: `src/vtesbot/engine/state.py` (`AllyInPlay`), `src/vtesbot/
  engine/allies.py` (`detect_contest_on_recruit`), `src/vtesbot/engine/
  observation.py` (`AllyView`, `build_observation`), `src/vtesbot/engine/
  phases/minion.py` (`_perform_recruit_ally`'s call site), `src/vtesbot/
  engine/__init__.py` (export). Card registration is unchanged: 47th Street
  Royals stays `blocked`/`OQ-14` (superseded reason tracked there, now
  pointing at OQ-15 for the remaining prerequisite) -- re-implementing it,
  and the five other now-confirmed unique allies plus Shilmulo Tarot, is
  `card-implementer`'s job.
  OQ-14 documents the specific re-confirmation and keeps 47th Street Royals
  blocked on this entry until it is resolved; this entry's own analysis and
  "what would be needed" above are unchanged and still the actual fix needed.

## OQ-11: Carrying an early hook effect forward -- Bonding (status: resolved)

- Situation: found by `card-implementer` while re-attempting Bonding after
  OQ-9's resolution. Card text (verified live via `krcg.load()`, card id
  `100236`, 2026-10-09, matching `data/cards/100236.json`): "Only usable
  during a bleed action.\n[dom] +1 bleed (limited).\n[DOM] +1 stealth and
  +1 bleed (limited)." Rulings (verbatim): "[DOM] Cannot be used if you do
  not need the stealth at the time you play it." [TOM 19951109]; "[DOM]
  Cannot be used to increase the stealth of a non-bleed action." [LSJ
  19980824] [RTR 19941109]. Not a ruling ambiguity -- the text and rulings
  are explicit and consistent. The block is a missing engine capability,
  distinct from OQ-9
  (which is fully resolved and is necessary but not sufficient here).
- The basic clause ("[dom] +1 bleed (limited)") is clean and would be
  implementable exactly like `src/vtesbot/cards/threats.py`
  (`"bleed_amount_modifier"` hook only, no cross-window issue) -- but the
  registry models a card as either fully implemented or blocked, not a
  partial implementation of only the clean clause (see below), so this
  clause is not wired either while the card as a whole stays blocked.
- The superior clause is one single card play that must produce *two*
  effects at once: "+1 stealth" (which can only matter if applied during
  the block-attempt phase, before the bleed is known to be unblocked) and
  "+1 bleed" (which can only be read by `_perform_bleed`'s `resolve()`,
  which runs *after* the block-attempt phase concludes, per
  `engine/action.py::perform_minion_action`'s "announce (lock) -> block
  attempt -> resolve" ordering). OQ-9 added the `action` discriminator to
  the `"stealth_modifier"`/`"intercept_modifier"` hook context, which lets a
  provider correctly gate the stealth half on `action == ACTION_BLEED` --
  but it does not give a provider any way to also deliver the bleed half
  from that same hook application, because:
  1. `"stealth_modifier"`'s `apply(state) -> int` contract is consumed by
     `_duel_stealth_intercept`'s `stealth += delta`; nothing else reads its
     return value, so a second number cannot be smuggled back through it.
  2. The only object that models "the pending bleed amount for this
     action", `amount_box`, does not exist yet at the time the stealth
     window runs: `_perform_bleed`'s `resolve()` closure (the only place
     that constructs `amount_box = [base_amount]`) is not invoked until
     *after* `attempt_block` (and therefore the entire stealth/intercept
     ping-pong) has already returned, per `perform_minion_action`'s own
     body (`blocker = attempt_block(...); ...; resolve()`). There is no
     shared, mutable, per-action container reachable from *both* the
     stealth window's `apply()` and the later `resolve()`/amount-window
     computation -- confirmed by reading `engine/action.py`,
     `engine/phases/minion.py`, and grepping `engine/` for any existing
     per-vampire/per-action scratch field (`scratch`, `pending`, `metadata`
     all return no hits besides an unrelated comment in `combat.py`).
  3. Applying the "+1 bleed" as an *immediate*, separate `lose_pool` call at
     stealth-apply time (bypassing the later amount window entirely) was
     considered and rejected: it desynchronizes from `resolve()`'s own
     floor-at-0 clamp (`amount = max(0, amount_box[0])`) and from the
     Edge-holder check (`if amount >= 1: state.edge_holder = player`, which
     only inspects `resolve()`'s own locally-computed `amount`). Worked
     example: base bleed 1, Bonding superior +1 (applied immediately,
     unclamped) = 1 pool already lost; a later Telepathic Counter -2 in the
     amount window reduces `resolve()`'s own `amount_box` (starting from
     the *un-bumped* base of 1, since Bonding's +1 never reached it) to
     `max(0, 1-2) = 0`. Total pool lost = 1 (immediate) + 0 (window) = 1,
     and no Edge transfer -- but the *correct*, single combined total per
     the rules would be `max(0, 1+1-2) = 0` pool lost, same Edge result.
     The split-call approach overcharges the defender by 1 pool in this
     case: a real mis-resolution, not merely an equivalent re-ordering (this
     is the same category of "byte-for-byte equivalent timing" reasoning
     `telepathic_counter.py`'s own docstring uses to justify a *different*
     timing simplification for a card with no stealth-window interaction --
     it does not extend to Bonding, precisely because Bonding's early
     half has an effect, the stealth bump, that the late window cannot
     reproduce, which is exactly why OQ-9 existed).
  4. Storing the pending flag on `VampireInPlay.attachments` (an existing,
     engine-exposed field) was also considered and rejected: that field's
     documented semantics (`engine/cards.py::CardAttachment`,
     `engine/attachments.py`) are for a *persistent* attached card
     (Discipline/archetype masters, equipment, retainers), consulted by
     `effective_capacity`/`effective_disciplines` every time either is
     read anywhere in the engine (e.g. by a wholly unrelated vampire's
     discipline check); misusing it as a one-shot transient marker for an
     Action Modifier card (which Rulebook SS2 says goes to the ash heap
     immediately on play, never stays "on" anything) would leak a fake
     discipline-level/capacity contribution into every other read of that
     vampire's effective stats for as long as the marker lived, and is
     exactly the "hack around a missing engine mechanism inside the card
     module" CLAUDE.md forbids.
- What would be needed: a per-minion-action pending-modifier carryover --
  e.g., `perform_minion_action`/`_perform_bleed` constructing one shared
  mutable scratch container *before* `attempt_block` runs (not only inside
  `resolve()`, as today), threading it into both the
  `"stealth_modifier"`/`"intercept_modifier"` hook context and the later
  `"bleed_amount_modifier"` hook context, so a provider's earlier `apply()`
  can leave something for its own later provider call to pick up and fold
  into the *same* clamped `amount_box` computation. This is `rules-engineer`
  scope (`engine/action.py` and its caller `engine/phases/minion.py`), not
  something a card module may build around.
- Impacted code: `src/vtesbot/engine/action.py`,
  `src/vtesbot/engine/phases/minion.py`. Impacted cards: Bonding (registered
  `blocked`, reason `OQ-11` -- superseding the now-resolved `OQ-9` as this
  card's blocking reason; OQ-9's own fix remains necessary groundwork,
  reused once this gap closes).
- Resolution (`rules-engineer` pass): built exactly the "what would be
  needed" mechanism described above, with no new ruling required (the block
  was always an engineering gap, not an unsettled rule). `engine/
  action.py::perform_minion_action` now constructs one shared, mutable
  `pending: dict[str, Any] = {}` *before* `attempt_block` runs (not only
  inside `resolve`, which was the point of failure OQ-11 identified), and
  threads the same object through two paths: into `attempt_block` ->
  `_duel_stealth_intercept`, whose hook context already carried `action`
  (OQ-9) and now also carries `pending` (`context["pending"]`) for every
  `"stealth_modifier"`/`"intercept_modifier"` offer of that block attempt;
  and into `resolve` itself, whose signature changed from
  `Callable[[], None]` to `Callable[[dict[str, Any]], None]` so a caller's
  own later hook window can read the same object back.
  `engine/phases/minion.py::_perform_bleed`'s `resolve` closure folds
  `pending.get(PENDING_BLEED_AMOUNT_KEY, 0)` (a new named scratch-key
  constant, `PENDING_BLEED_AMOUNT_KEY = "bleed_amount_bonus"`) into
  `base_amount` *before* building `amount_box`, so an earlier stealth-window
  stash participates in the exact same `max(0, amount_box[0])` clamp-at-0
  and `if amount >= 1: state.edge_holder = player` check as every other
  bleed-amount contribution -- resolving the overcharge OQ-11's point 3
  identified (the rejected "apply immediately" alternative lost 1 extra
  pool in that worked example; this fix reproduces the correct combined
  total). `pending` is also threaded into the `"bleed_amount_modifier"`
  window's own context (`context={"vampire": ..., "amount": amount_box,
  "pending": pending}`), so a provider registered there can inspect it too,
  not only a provider registered on the earlier stealth/intercept hooks.
  `_perform_hunt`'s `resolve` closure gained the same `pending` argument
  (required by the shared `perform_minion_action` call-site signature) but
  ignores it, since hunt has no later window needing it. `attempt_block` and
  `_duel_stealth_intercept` both accept `pending` as an optional parameter
  defaulting to a fresh empty dict, so `political_action`
  (`engine/politics.py`, which calls `attempt_block` directly with no later
  window of its own to feed) and every pre-existing test that does not pass
  `pending` are unaffected -- confirmed zero-regression: all 146
  previously-passing tests still pass unmodified.
  Proven end-to-end by `tests/rules/test_pending_modifier.py`: a fake
  `"stealth_modifier"` provider (stand-in for Bonding's superior clause)
  that both bumps stealth and stashes a bleed bonus from the *same*
  `apply()` call, with the stashed value surviving into `_perform_bleed`'s
  `resolve` and correctly combining with a later `"bleed_amount_modifier"`
  reduction under one shared clamp (the exact worked example from this
  entry's point 3, confirming the overcharge no longer occurs), plus
  zero-regression checks (default-empty `pending`, no-providers-registered,
  and hunt ignoring the new argument without error).
  **Not** touched, per this task's explicit scope: `src/vtesbot/cards/
  bonding.py` stays `blocked`/`OQ-11` in the registry -- wiring Bonding
  itself against this capability (its two providers: one on
  `"stealth_modifier"` gated on `action == ACTION_BLEED` that both adds +1
  stealth and stashes +1 under `PENDING_BLEED_AMOUNT_KEY`, and the basic
  clause's existing clean `"bleed_amount_modifier"` pattern) is
  `card-implementer`'s job in a follow-up pass.
- `rules-auditor` review (independent, read-only): confirmed the fix is
  correct and a genuine same-object thread end-to-end (hand-traced, not just
  trusted from the test), confirmed zero regression to the existing
  stealth/intercept alternation and to `political_action`, re-verified the
  worked numeric example against the actual clamp/edge-holder code, found no
  Bonding-specific logic in `engine/`, and re-ran the full suite/lints
  itself (152 passed, clean). No blockers, no majors. Two minor,
  non-blocking notes for future vigilance when the next card uses `pending`:
  (1) `Decision.context` for `"stealth_modifier"`/`"intercept_modifier"`
  now carries the live, still-mutable `pending` dict (a shallow `dict(context)`
  copy, but the nested object is shared) -- harmless today since no stashed
  value is anything other than "this card was played," already public once
  chosen, but a future card whose stash encodes something not otherwise
  public would leak it into the *opposing* player's own hook `Decision` one
  window early; (2) relatedly, `pending` is a live reference, not a
  defensive per-offer snapshot, so a future `Agent.decide` implementation
  that mutated `decision.context` as scratch space of its own would corrupt
  it. Neither applies to any card in the pool today; flag for
  `rules-engineer`/`rules-auditor` to re-check once a second card registers
  against `pending`.
- `card-implementer` follow-up (Bonding, krcg 100236, now wired): built
  exactly the two providers the `rules-engineer` resolution above named --
  a `"stealth_modifier"` provider for the superior clause, gated on
  `context.get("action") != ACTION_BLEED`, whose `apply()` both returns `1`
  (stealth) and stashes `pending[PENDING_BLEED_AMOUNT_KEY] =
  pending.get(PENDING_BLEED_AMOUNT_KEY, 0) + 1` (bleed), and a clean
  `"bleed_amount_modifier"` provider for the basic clause, byte-for-byte
  `threats.py`'s own pattern. One correction to the resolution's own
  phrasing: the basic clause is *not* gated on `action == ACTION_BLEED` --
  verified directly against `engine/phases/minion.py::_perform_bleed`'s
  `resolve()` closure, the `"bleed_amount_modifier"` hook's context carries
  no `"action"` key at all (only `"stealth_modifier"`/`"intercept_modifier"`
  do, per OQ-9); such a gate would silently read `None != "bleed"` and
  suppress the clause entirely. It relies on hook selection alone (the hook
  is only ever offered from a bleed's own resolution step), exactly as
  `threats.py` already documented for itself. Re rules-auditor's two flagged
  vigilance notes above (Bonding being the second card to register against
  `pending`): neither materializes here -- Bonding's own stash is just an
  integer bleed bonus tied to a play that is already public the instant it
  is chosen, not otherwise-hidden information, so the `Decision.context`
  leak note does not expose anything new, and no `Agent.decide`
  implementation in the pool mutates `decision.context`.
  Additionally closed a related, previously-undiscovered "(limited)"
  cross-card gap found while wiring the superior clause's interaction with
  Threats (both are bleed-increasing "(limited)" action modifiers, but
  Bonding's superior clause acts in the *earlier* stealth window while
  Threats only ever acts in the *later* `"bleed_amount_modifier"` window):
  `vtesbot.cards._shared.bleed_bookkeeping` previously keyed its "(limited)"
  bookkeeping off `_perform_bleed`'s `resolve()`-local `amount_box`, which
  only exists during the later window and so could not see a "(limited)"
  increase played earlier in the same action from the stealth window --
  Threats could have silently stacked its own +1/+2 on top of Bonding's
  superior stash, a real rules violation (SS8 "cannot be played to increase
  the bleed if the bleed amount is already being increased by another
  action modifier card"), not merely a hypothetical one, since both cards
  are implemented and legal together. Fixed by re-keying `bleed_bookkeeping`
  off `pending` instead (same per-action lifetime, now spanning both hook
  windows instead of only the later one) and updating `threats.py`/
  `telepathic_counter.py`'s own calls accordingly -- a small, behaviour-
  preserving refactor for both already-implemented cards (no test for either
  exercises `bleed_bookkeeping` directly, and both cards' existing test
  suites still pass unmodified). Proven by
  `tests/cards/test_bonding.py::test_bonding_superior_blocks_a_later_threats_play_via_the_shared_limited_flag`.
  All clauses/rulings covered by `tests/cards/test_bonding.py` (16 tests);
  full suite green (168 passed), `ruff check`/`ruff format --check` clean.
  Bonding is now `Status.IMPLEMENTED` in the registry; this OQ stays closed.

## OQ-12: "Recruit ally" action not wired -- 47th St. Royals (status: resolved)

- Situation: found by `card-implementer` while re-attempting 47th Street
  Royals after OQ-7's resolution. OQ-7 landed `AllyInPlay`
  (`engine/state.py`), `recruit_ally`/`burn_ally` (`engine/allies.py`), and
  full `Observation` visibility (`engine/observation.py`) for an ally
  already in play -- enough for a *scenario test* to put the card's ally in
  play directly (`tests/rules/test_allies.py`) and prove its own burn-to-
  reduce-bleed reaction. But nothing in a real game ever calls
  `recruit_ally` for a player-controlled card: `src/vtesbot/engine/phases/
  minion.py`'s own module docstring states "all other minion actions
  (equip, political action, leave torpor, diablerie, become Anarch, etc.)
  are out of scope and are never offered" -- a milestone-2 scope limit
  confirmed still in force by reading `_choose_and_perform_action`, whose
  only two offered choices are `ACTION_BLEED`/`ACTION_HUNT`
  (`engine/action.py`'s named constants); "recruit ally" is not among them,
  and no other call site in `engine/` offers it either. This is distinct
  from OQ-7 (which is fully resolved -- the ally *representation* exists and
  works) and is a new, more precise gap: there is still no legal way for a
  player to actually play this card from hand into the ready region in a
  real game, independent of the ally representation itself.
- What would be needed: a "recruit ally" minion action, offered alongside
  bleed/hunt in `_choose_and_perform_action` (or as its own library-card
  play analogous to a master-phase play, since recruiting an ally is itself
  how the ally *enters* play -- Rulebook SS4 default actions: "recruit ally
  (undirected, +1 stealth; recruited ally cannot act this turn)"), with its
  own announce/block-attempt window mirroring
  `engine/action.py::perform_minion_action`, whose `resolve()` would call
  the already-built `recruit_ally`. This is `rules-engineer` scope (`engine/
  phases/minion.py` and/or `engine/action.py`), not something a card module
  may build around -- `card-implementer` does not attempt to wire this
  itself per CLAUDE.md "No engine patches."
- Impacted code (at the time this was opened): `src/vtesbot/engine/phases/
  minion.py`, `src/vtesbot/engine/action.py`. Impacted cards: 47th Street
  Royals (registered `blocked`, reason `OQ-12` -- superseding the now-resolved
  `OQ-7` as this card's blocking reason; OQ-7's own fix remains necessary
  groundwork, reused once this gap closes). Also relevant to OQ-10 (contested
  unique allies), which is itself gated on this same missing action ever
  becoming reachable.
- Sources re-read before implementing (`rules-engineer` pass, per this
  entry's own mandatory procedure): the local rulebook cache,
  `data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md`
  ("Recruit Ally" section and "Action Card (or Card in Play)"/"Summary of the
  Course of an Action"/"Announce the Action"/"Resolve the Action"
  subsections), quoted verbatim below where load-bearing.
  1. **Who/cost/target/stealth** (the "Recruit Ally" section itself): "Who
     can recruit an ally: Any ready minion." / "Cost: As listed on the ally
     card." / "Default target: None. Undirected action." / "Default
     stealth: +1 stealth." / "Effect: Allies are action cards that become
     minions in their own right ... If the action is successful, the ally is
     placed in your ready region, but they cannot act this turn. When an
     ally is brought into play, they receive blood counters from the blood
     bank to represent their life (listed on the ally's card)."
  2. **When the card leaves hand, and what happens on a block** ("Announce
     the Action" / "Resolve the Action", general to *every* action built
     from a played card, not specific to allies): "Any card required for the
     action is played (face up) at this time, but is temporarily set aside
     (out of play) until the action resolves." / "If the action is
     successful ..., then the cost of the action is paid and the effects of
     the successful action take place. If the action is blocked, then any
     card played to perform the action is burned ... Note that the action's
     cost, if any, is only paid if the action succeeds; the cost is not paid
     if the action is blocked."
  3. **Worked example in the same section** (Dowager/Underbridge Stray,
     "Recruit Ally" section and "Announce the Action"): confirms "undirected"
     concretely ("It can be blocked by the ready unlocked minions of Sarah's
     prey or Sarah's predator") and that the cost is deferred ("The blood is
     not paid until the action succeeds").
- Resolution (`rules-engineer` pass): built the "recruit ally" minion action
  on top of OQ-7's `AllyInPlay`/`recruit_ally` (`engine/state.py`,
  `engine/allies.py`), mirroring `engine/phases/master.py`'s
  `"master_phase_play"` hook pattern (CLAUDE.md SS6: the engine exposes a
  hook, card-specific stats/identity are supplied by the registering
  `src/vtesbot/cards/` module, never guessed or special-cased by the
  engine) rather than extending `engine/cards.py::LibraryCard` with new
  generic stat fields -- no other part of the engine parses a library
  card's own printed numbers yet (no deck-import pipeline exists per
  CLAUDE.md's own milestone order), and the hook-based design needed no such
  pipeline: a future Ally card module supplies its own life/strength/bleed/
  cost directly, the same way `celerity.py`/`life_in_the_city.py` already
  supply their own numeric effects.
  - `engine/action.py`: added `ACTION_RECRUIT_ALLY` (OQ-9's discriminator
    family) and a new `on_blocked: Callable[[dict[str, Any]], None] | None`
    parameter on `perform_minion_action`, generalizing (not recruit-ally-
    specific; reusable by a future equip/employ-retainer action) source 2
    above: called -- instead of `resolve` -- if the action is blocked,
    *after* `run_combat` (source 2's "burned"/"simultaneous consequences"
    text does not mandate a code ordering relative to combat resolution
    itself; `run_combat` has no dependency on whether the played card has
    been burned yet, so this ordering is implementation detail, not a rules
    question). Bleed/hunt pass nothing (default `None`), so this is
    zero-regression for them.
  - `engine/allies.py`: added `RecruitAllySpec` (`card: LibraryCard, life:
    int, strength: int = 0, bleed: int = 0, pay_cost: Callable[[GameState],
    None] | None = None`) -- the contract a `"recruit_ally_play"` hook
    option's `apply(state)` must return. `recruit_ally`/`burn_ally`
    themselves are unchanged.
  - `vtesbot/cards/_shared.py`: added `play_from_hand_pending` (pop from
    hand + draw replacement, but do *not* yet append to the ash heap --
    source 2's "temporarily set aside ... until the action resolves");
    `play_from_hand` is now a thin wrapper (`play_from_hand_pending` +
    immediate ash-heap append), a behaviour-preserving refactor for every
    existing caller (Life in the City, Bonding, Threats, Telepathic
    Counter), since a play with no block-attempt window of its own always
    had a certain fate the instant it was played.
  - `engine/phases/minion.py`: added `RECRUIT_ALLY_PLAY_HOOK =
    "recruit_ally_play"` and `RECRUIT_ALLY_STEALTH = 1` (source 1's "+1
    stealth"), and `_perform_recruit_ally`, which calls the chosen hook
    option's `apply(state)` immediately (source 2's announce-time card
    removal, via `play_from_hand_pending` inside the provider), then runs
    `perform_minion_action` with a `resolve` that pays the spec's
    `pay_cost` (if any) and calls `recruit_ally` only on success, and an
    `on_blocked` that appends the already-removed card to the ash heap on a
    block (source 2's "burned"; "cost ... is not paid"). `_choose_and_
    perform_action` folds every currently-offered `"recruit_ally_play"`
    option directly into the same top-level `action_choice` decision
    alongside `ACTION_BLEED`/`ACTION_HUNT` (one choice per recruitable Ally
    card already identifies its own action, same granularity bleed/hunt
    already have -- no separate "pick action type, then pick which ally"
    step was needed). With no Ally card module registered against the hook
    yet, `hooks.offer` returns `[]` and `action_choice` degrades to exactly
    the pre-OQ-12 bleed/hunt pair (confirmed zero-regression: all 168
    previously-passing tests still pass unmodified).
  - Scope boundary carried over from OQ-7, re-confirmed rather than
    silently extended: source 1's "Who can recruit an ally: Any ready
    minion" literally includes a ready unlocked *ally*, not only a vampire.
    `_perform_recruit_ally` is reachable only from `_choose_and_perform_
    action`, which `minion_phase` calls only for ready unlocked *vampires*;
    extending this to allies-as-actor is not done here, both because no card
    in the pool needs it and because `engine/phases/unlock.py` does not
    unlock allies at all yet (a recruited ally, entered `locked=True`, can
    in practice never become ready-unlocked under current code regardless),
    so building it now would be guessing ahead of a sourced need (CLAUDE.md
    rule 2) rather than resolving one. Documented explicitly in
    `engine/allies.py`'s and `engine/phases/minion.py`'s module docstrings
    as a known, deliberate limit, not an oversight.
  - Proven by `tests/rules/test_recruit_ally_action.py`: eligibility (not
    offered with no provider registered; not offered when the provider's
    own card is not yet in hand; offered once it is), the full success path
    (card leaves hand immediately, never reaches the ash heap, cost paid
    only on success, ally enters play `zone="ready"`/`locked=True`), the
    full blocked path (card burned to the ash heap, cost never paid, no
    `AllyInPlay` created, the blocking vampire genuinely locks and enters
    combat -- using a fake `"intercept_modifier"` reaction provider to make
    the block actually succeed against the +1 stealth baseline, the same
    technique `test_action_discriminator.py`'s hunt test already needed),
    the +1 stealth baseline itself via `perform_minion_action` directly, and
    `on_blocked`'s generic contract (fires exactly on a block, `resolve`
    exactly otherwise, never both) independent of recruit ally specifically.
  - **Not** touched, per this task's explicit scope: `src/vtesbot/cards/
    forty_seventh_street_royals.py` stays `blocked`/`OQ-12` in the registry
    -- wiring its own `"recruit_ally_play"` provider (and its own cost,
    which is `None` per krcg, so no `pay_cost` closure is actually needed for
    this specific card) against this capability is `card-implementer`'s job
    in a follow-up pass. OQ-10 (contested unique allies) remains open and is
    now live rather than latent once that follow-up pass lands, since
    `recruit_ally` is reachable from a real game for the first time; OQ-10's
    own text already anticipated this.
  - Flagged for `rules-auditor`: this is a core engine sequencing change
    (`perform_minion_action`'s new `on_blocked` branch, a new top-level
    minion-phase action, and a refactor of `play_from_hand`/addition of
    `play_from_hand_pending` touching every existing card module that plays
    a card) and should get an independent read-only review before
    `card-implementer` touches 47th Street Royals, per CLAUDE.md SS7.

## OQ-13: recruit_ally_play omits acting-vampire id (status: resolved)

- Situation: found by `card-implementer` while re-attempting 47th Street
  Royals now that OQ-12 is resolved. Card text (verified live via
  `krcg.load()`, card id `102217`, 2026-10-09, matching
  `data/cards/102217.json`):
  "Unique mortal with 2 life. 1 strength, 0 bleed. You can burn 47th Street
  Royals to reduce a bleed against you by 3." `rulings == []`.
  `clan_requirement == ["Brujah"]` per krcg -- not itself a ruling ambiguity
  (the printed field and the rulebook's general rule for what a clan
  requirement on a library card means, below, are both explicit and
  consistent); the block is a missing piece of engine context, distinct from
  OQ-12 (which only resolved whether a "recruit ally" action exists at all).
- Who the clan requirement binds to (not a guess -- Rulebook SS2 "Card
  Types", live-fetched and cross-checked against the local cache
  `data/sources/rulebook/2026-10-09/2-card-types.md`, quoted verbatim):
  "**Requirements for Playing Cards** ... Only a minion who meets the
  requirements given on a minion card can play it, whereas only a
  Methuselah who controls a ready minion who meets the requirements of a
  master card can play it." The rulebook draws this contrast deliberately,
  in the same sentence: a *minion* card's requirement binds to the specific
  acting minion that plays it; a *master* card's requirement binds only to
  "the Methuselah controls a ready minion meeting it", not to which minion
  is "acting" (master cards are not played by a specific minion at all). Ally
  cards are explicitly categorized as minion cards, not master cards: "Minion
  Cards: Minion cards are cards that your vampires and allies (collectively
  referred to as 'minions') play" (same source), and "Recruit Ally" (Rulebook
  SS4, quoted in OQ-12's own resolution) is itself performed by "any ready
  minion" -- i.e. recruiting 47th Street Royals is playing a minion card,
  and the specific minion attempting the recruit (not merely some other
  vampire the Methuselah happens to also control) must itself be Brujah.
  This settles the ruling question the task that opened this entry flagged
  as needing care ("controls a vampire of the required clan" vs. "is played
  by a vampire of the required clan"): the correct, sourced reading is the
  latter.
- What's missing structurally: `_choose_and_perform_action`
  (`src/vtesbot/engine/phases/minion.py`) already has the specific acting
  vampire in scope (its own `vampire: VampireInPlay` parameter -- the one the
  player already committed to via the earlier `"act_with:<id>"` choice in
  `minion_phase`'s loop) at the point it calls `hooks.offer(
  RECRUIT_ALLY_PLAY_HOOK, state, player=player)`, but does not forward it:
  the context built for that `offer()` call is `{"player": player}` only.
  Multiple vampires can be simultaneously ready-unlocked for one Methuselah
  (`state.ready_unlocked_vampires(player)` can return more than one), and
  `vampire.locked` is not set `True` until *after* this `offer()` call
  returns (inside `perform_minion_action`, called later by
  `_perform_recruit_ally`) -- so nothing reachable from `GameState` at
  `offer()` time identifies which of possibly several ready-unlocked
  vampires is the one currently attempting to act. A `"recruit_ally_play"`
  provider therefore cannot correctly gate on the acting vampire's own clan:
  checking "does `player` control *some* ready-unlocked Brujah vampire
  anywhere" instead would silently offer the recruit option even when the
  player chose to act with a *different*, non-Brujah vampire this impulse
  (a real mis-resolution, not a hypothetical edge case -- two ready-unlocked
  vampires of different clans is an ordinary mid-game state), and the
  opposite shortcut (only ever offering it when *every* ready-unlocked
  vampire happens to be Brujah) would incorrectly withhold a legal recruit
  attempt whenever an unrelated non-Brujah vampire also happens to be ready.
  Neither approximation is correct; this is not something a card module may
  work around internally (CLAUDE.md "No engine patches").
- What would be needed: thread the acting vampire's identity (e.g.
  `vampire=vampire.instance_id`, mirroring how `_perform_bleed` already
  passes `"vampire": vampire.instance_id` into `BLEED_AMOUNT_MODIFIER_HOOK`'s
  own context) into `_choose_and_perform_action`'s
  `hooks.offer(RECRUIT_ALLY_PLAY_HOOK, state, player=player)` call, so a
  provider can look the vampire up (`state.players[player].vampires[...]`)
  and check its `card.clan` before deciding whether to offer anything. This
  is `rules-engineer` scope (`engine/phases/minion.py`), not something
  `card-implementer` may add itself.
- Impacted code (at the time this was opened):
  `src/vtesbot/engine/phases/minion.py` (`_choose_and_perform_action`'s
  `hooks.offer(RECRUIT_ALLY_PLAY_HOOK, ...)` call site). Impacted cards:
  47th Street Royals (registered `blocked`, reason `OQ-13` -- superseding
  the now-resolved `OQ-12` as this card's blocking reason, the same way
  `OQ-12` superseded `OQ-7` and `OQ-11` superseded `OQ-9`; none of OQ-7's,
  OQ-12's or this entry's own groundwork is wasted -- all three remain
  necessary, just not yet sufficient).
- Not blocked by this gap, and not re-litigated: the card's own reaction
  ("You can burn 47th Street Royals to reduce a bleed against you by 3") has
  no dependency on which vampire recruited it or on `RECRUIT_ALLY_PLAY_HOOK`
  at all -- it remains fully provable against the already-wired
  `"bleed_amount_modifier"` hook exactly as OQ-7's and OQ-12's own entries
  already documented (`tests/rules/test_allies.py::
  test_ally_burned_as_a_bleed_reduction_reaction_cost`). Per the registry's
  established all-or-nothing convention (CLAUDE.md SS6; see OQ-9's own entry:
  "the registry models a card as either fully implemented or blocked, not a
  partial implementation of only the clean clause"), this clean half is
  still not wired into the real `src/vtesbot/cards/
  forty_seventh_street_royals.py` module while the recruit side stays
  blocked -- exactly the precedent OQ-9/OQ-11 already set for Bonding's own
  clean basic clause.
- OQ-10 (contested unique allies): re-read in full while revisiting this
  card. Still correctly out of scope/latent, not live: OQ-10's own text
  anticipated it would become live "once [the OQ-12 follow-up] pass lands,
  since `recruit_ally` is reachable from a real game for the first time" --
  but with 47th Street Royals itself still blocked (now on this entry
  instead of OQ-12), no card in the pool can actually be recruited by either
  Methuselah in a real game yet, so nothing can create two controllers'
  copies of the same unique ally. OQ-10 remains open but latent until both
  this entry and OQ-10 itself are resolved.
- Resolution (`rules-engineer` pass): threaded the acting vampire's own
  identity into the one call site this entry identified --
  `src/vtesbot/engine/phases/minion.py::_choose_and_perform_action`'s
  `hooks.offer(RECRUIT_ALLY_PLAY_HOOK, state, player=player)` now also
  passes `vampire=vampire.instance_id` (`vampire` was already the function's
  own parameter -- the acting vampire the player committed to via the
  earlier `"act_with:<id>"` choice in `minion_phase`'s loop), mirroring the
  pattern `_perform_bleed` already used for `BLEED_AMOUNT_MODIFIER_HOOK`'s
  own context. No new ruling was needed -- this entry's own "What's missing
  structurally"/"What would be needed" paragraphs had already settled the
  reading (Rulebook SS2 "Card Types" > "Requirements for Playing Cards") and
  identified the exact fix; this pass is pure plumbing, deliberately scoped
  to that one context key and nothing else.
  - A `"recruit_ally_play"` provider can now call
    `state.players[context["player"]].vampires[context["vampire"]]` to
    recover the specific acting `VampireInPlay` and inspect its
    `card.clan` before deciding whether to offer anything -- the capability
    47th Street Royals' own clan requirement (`clan_requirement ==
    ["Brujah"]` per krcg) needs, distinguishing "the acting vampire is
    Brujah" from the incorrect "the Methuselah controls *some* Brujah
    vampire" or "every ready-unlocked vampire happens to be Brujah"
    approximations this entry's situation paragraph ruled out.
  - Proven by `tests/rules/test_recruit_ally_action.py::
    test_recruit_ally_play_hook_context_carries_the_acting_vampires_
    identity`: two simultaneously ready-unlocked vampires on the same
    Methuselah, a stub provider gated on `context["vampire"]` matching one
    specific `instance_id` -- acting with the *other* ready-unlocked vampire
    first does not surface the option at all; acting with the matching one
    does. Confirms the exact mis-resolution this entry flagged (an
    unrelated ready-unlocked vampire silently unlocking the option) cannot
    happen. Full suite re-run green (175 passing, up from 174 -- one new
    test, zero regressions) alongside `ruff check`/`ruff format --check`.
  - **Not** touched, per this task's explicit scope and this entry's own
    "Impacted code" note: `src/vtesbot/cards/forty_seventh_street_royals.py`
    stays `blocked`/`OQ-13` in the registry -- wiring its own
    `"recruit_ally_play"` provider against this now-available context is
    `card-implementer`'s job in a follow-up pass (same handoff shape as
    OQ-9 -> OQ-11 -> Bonding and OQ-7 -> OQ-12 -> the recruit-ally action
    itself). OQ-10 (contested unique allies) remains open and latent for the
    same reason OQ-12's own resolution already gave: no card in the pool can
    yet actually be recruited by either Methuselah in a real game until that
    follow-up card-implementer pass lands.
  - Flagged for `rules-auditor`: engineering-gap fix on the same core
    sequencing surface (`engine/phases/minion.py`) that OQ-9/OQ-11/OQ-12
    already had independently reviewed; recommend review before
    `card-implementer` touches 47th Street Royals again, per CLAUDE.md SS7.

## OQ-14: 47th St. Royals recruit makes OQ-10 live (status: resolved, see OQ-15)

- Situation: found by `card-implementer` while re-attempting 47th Street
  Royals now that both OQ-12 (the recruit-ally action itself) and OQ-13 (the
  acting-vampire identity needed for this card's own clan gate) are resolved.
  Card text re-verified live this pass (`krcg.load()`, a fresh in-process
  fetch, 2026-10-09, cross-checked byte-for-byte against `data/cards/
  102217.json` and against the active 2P list `data/formats/2p/
  2026-10-03.json`, which lists `krcg_id: 102217`): "Unique mortal with 2
  life. 1 strength, 0 bleed. You can burn 47th Street Royals to reduce a
  bleed against you by 3." `rulings == []`. `clan_requirement ==
  ["Brujah"]`. `cost is None`. `burn_option is False`. Unchanged from OQ-7/
  OQ-12/OQ-13's own quotes. Not a ruling ambiguity -- the printed "Unique"
  and the already-settled Rulebook SS4 Advanced Rules > Contested Cards text
  (quoted verbatim in OQ-10's own entry: "If more than one unique card with
  the same name is brought into play, that means control of the card is
  being contested. For the duration of the contest, all of the contested
  cards are turned face down and are out of play") are both explicit. The
  block is that wiring this specific card's own `"recruit_ally_play"`
  provider now makes OQ-10's already-filed, already-open gap reachable in an
  ordinary legal game for the first time, not merely a latent/future concern
  as OQ-10's and OQ-12's own entries both explicitly anticipated it would
  eventually become.
- Why this is reachable now, not hypothetical: 2P decks are built
  independently (CLAUDE.md SS3), exactly like the crypt-side contested-
  vampire scenario the 2P variant already handles explicitly
  (`engine/contests.py`). "Unique" restricts a single Methuselah to at most
  one copy of a given card in their own deck (ordinary VTES deck-
  construction convention), not across the whole format -- nothing stops
  each player from independently including their own single copy of 47th
  Street Royals in their own 60-card library, each with their own eligible
  ready-unlocked Brujah vampire recruiting it on their own turn. With OQ-12
  and OQ-13 both resolved, two ordinary 2P-legal decks (no unusual or illegal
  build required) can now reach this sequence of in-game decisions for the
  first time.
- Re-confirmed by grep, this pass, not assumed, that the engine still has
  zero uniqueness enforcement for an ally, unlike a vampire:
  - `engine/contests.py::detect_contest_on_reveal`'s only call site, project-
    wide, is `engine/phases/influence.py` (a vampire's reveal into the
    ready/torpor region); it is never called from `engine/allies.py::
    recruit_ally` or `engine/phases/minion.py::_perform_recruit_ally`.
  - `engine/state.py::AllyInPlay` has no `contested_with` field at all
    (unlike `VampireInPlay.contested_with`).
  - `recruit_ally` performs no check against any existing ally already in
    play (either player's) by name/krcg_id before creating a new
    `AllyInPlay`.
  - `engine/observation.py::AllyView`/`build_observation` show every in-play
    ally unconditionally to both players (OQ-7's own follow-up note), with
    no hidden/anonymized branch for a contested ally (unlike `VampireView`'s
    `contested` field and the uncontrolled-vampire anonymization already in
    place for vampires).
- Consequence if shipped as-is: if both Methuselahs each recruit their own
  copy of 47th Street Royals, the engine would silently create two
  independent, fully-visible `AllyInPlay` instances both named "47th Street
  Royals" under two different controllers -- not the Rulebook-mandated "face
  down and out of play for the duration of the contest" treatment. This is a
  genuine mis-resolution of the Unique rule (CLAUDE.md "never mis-resolves a
  card"), not a hypothetical edge case, the moment this card's own recruit-
  eligibility provider is wired into a real game.
- Not something this module may work around: CLAUDE.md "No engine patches"
  / "Do not hack around it inside the card module" -- a card-module-level
  same-name check would be an unsanctioned, incomplete substitute for OQ-10's
  own already-specified fix (contest tracking plus face-down/hidden
  treatment), not a legal implementation of the Rulebook's actual contested-
  card procedure, and would still miss the face-down/out-of-play visibility
  requirement entirely even if it somehow prevented a second recruit.
- What would be needed: OQ-10's own resolution, verbatim ("extend
  `AllyInPlay` with contest tracking mirroring `VampireInPlay.
  contested_with`/`engine/contests.py`, and give `AllyView`/
  `build_observation` a hidden/anonymized branch for a contested ally"),
  plus wiring `recruit_ally`/`_perform_recruit_ally` to call the ally-side
  equivalent of `detect_contest_on_reveal` once an ally is recruited. This is
  `rules-engineer` scope (`engine/state.py`, `engine/allies.py`,
  `engine/observation.py`), not something `card-implementer` may build
  around.
- Resolution (`rules-engineer` pass, 2026-10-09): OQ-10 itself is now
  resolved -- see its own entry for the full writeup (sourcing re-check,
  what was built, the quick sweep confirming six more unique allies (seven
  total) plus one unique Equipment are already 2P-legal and share this
  exact gap, and the one piece deliberately left for OQ-15). The specific
  mis-resolution this entry raised the alarm about -- "the engine would
  silently create two
  independent, fully-visible `AllyInPlay` instances ... not the
  Rulebook-mandated face down and out of play treatment" -- no longer
  happens: `recruit_ally`'s own production call site now detects the
  collision and both copies move to `zone == "contested"`, out of the
  usable ready region, proven end-to-end (not just at the lower-level
  helper) by `tests/rules/test_ally_contests.py::
  test_recruit_ally_action_end_to_end_detects_the_contest`.
  Not fully unblocked by this alone, though: OQ-10's own resolution
  deliberately left the unlock-phase pay-1-pool-or-yield resolution loop
  unbuilt (tracked as OQ-15, not a ruling ambiguity -- the cost/mechanism
  itself turned out to be directly sourced on the re-check, just not yet
  wired). Concretely, that means a contested ally today can correctly enter
  and remain "out of play," but no player can ever pay to keep contesting it
  or yield it -- the contest never ends. Whether that remaining gap is
  acceptable to ship against (a correctly-represented-but-permanently-stuck
  contest state is not a *mis*-resolution, just an incomplete one) or
  whether OQ-15 should land first is left for `card-implementer`'s own
  follow-up pass to weigh per this card's specific registration, per
  CLAUDE.md's "do not touch `forty_seventh_street_royals.py`" scope boundary
  this task was given. 47th Street Royals therefore stays `blocked` in the
  registry; its `blocked_reason` is `card-implementer`'s call to update
  (superseding to `OQ-15`, or something else) in that follow-up pass, not
  changed here.
- Not blocked by this gap, and not re-litigated: the card's own reaction
  ("You can burn 47th Street Royals to reduce a bleed against you by 3")
  still has no dependency on the recruit side or on uniqueness at all, and
  remains fully proven at the mechanism level by `tests/rules/
  test_allies.py::test_ally_burned_as_a_bleed_reduction_reaction_cost`
  (already exercising this card's own exact krcg_id and printed stats via a
  stand-in provider). Per the registry's established all-or-nothing
  convention (CLAUDE.md SS6; OQ-9/OQ-11's own precedent for Bonding's clean
  basic clause), this clean half stays unwired in the real module while the
  recruit side is unsafe to ship -- the registry models a card as either
  fully implemented or blocked, never a partial implementation of only its
  clean clause.
- Impacted code (at the time this was opened): none -- no engine files were
  touched by this entry itself (the gap was the one OQ-10 already named;
  this entry only re-confirmed it was live and named the specific card it
  blocks). Superseded by OQ-10's own resolution pass, which did touch
  `src/vtesbot/engine/state.py`, `engine/allies.py`, `engine/observation.py`,
  `engine/phases/minion.py` and `engine/__init__.py` -- see OQ-10's own
  "Impacted code". `src/vtesbot/cards/forty_seventh_street_royals.py`
  remains unchanged by this pass (out of scope, per this task's own
  instruction not to touch it) -- it still reads `Status.BLOCKED`,
  `blocked_reason="OQ-14"` in the registry; `card-implementer` decides, in
  the follow-up pass this entry's own Resolution note hands off to, whether
  to update that reason (e.g. to `OQ-15`) when reassessing the card.
  Impacted cards: 47th Street Royals (registered `blocked`, reason
  `OQ-14`, pending that follow-up); the five other unique allies and one
  unique Equipment OQ-10's quick sweep found (Double Deuce, Heartrender,
  Political Ally, Vagabond Mystic, The Vozhd of Juiz de Fora, The Vozhd of
  Sofia, Shilmulo Tarot) share the same now-resolved underlying gap, not yet
  registered at all.

## OQ-15: Ally/Equipment contest *resolution* loop not wired (status: resolved)

- Situation: found by `rules-engineer` while resolving OQ-10. Not a ruling
  ambiguity -- re-fetched live and cross-checked against the local cache
  (`data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md`, "Advanced
  Rules > Contested Cards"), the base rulebook rule gives the contest-
  resolution mechanism for *every* unique card in one unified paragraph: "The
  cost to contest a card is 1 pool, which you pay during each of your unlock
  phases. Instead of paying the cost to contest the card, you may choose to
  yield the card. A yielded card is burned ... If all other cards contesting
  your unique card are yielded, then the card is unlocked and turned face up
  during your next unlock phase, ending the contest." The 2P variant's own
  "Contested crypt cards" override (`data/sources/2p-variant/2026-10-09/
  variant.md`) changes only the face-down/out-of-play half of this, and only
  for crypt cards -- its own cost/resolution wording for crypt cards is
  identical pay-1-pool-per-unlock-or-yield. So for an ally (or equipment or
  location), the *same* mechanism already engine-side implemented for crypt
  cards (`engine/contests.py::resolve_one_contest`, wired into
  `engine/phases/unlock.py::_resolve_optional_effects_in_chosen_order`)
  applies, unmodified, with one difference: the contested copies are also
  out of play (not usable) for the whole duration, where a contested crypt
  card in 2P stays usable throughout.
- What's missing: nothing in `engine/phases/unlock.py` looks at
  `state.players[player].allies` at all -- `_pending_effect_ids` only
  iterates `vampires`. A contested ally (`AllyInPlay.contested_with` set,
  `zone == "contested"`, OQ-10's resolution) has no way to ever be offered a
  pay-or-yield decision, so once a contest begins it never ends in this
  engine today. This is a gap in engineering completeness, not an
  unresolved rules question -- deliberately scoped out of OQ-10's own pass
  (CLAUDE.md "small commits, one rule mechanism per change"; that task's own
  file list named `engine/state.py`/`engine/allies.py`/`engine/
  observation.py` specifically, not `engine/phases/unlock.py`).
- What would be needed: extend `engine/phases/unlock.py::_pending_effect_ids`
  to also surface one `f"contest_ally:{a.instance_id}"` entry per
  `player`'s own contested ally (mirroring the existing
  `f"contest:{v.instance_id}"` vampire entries), and an ally-side resolution
  function analogous to `engine/contests.py::resolve_one_contest` -- except
  yielding must leave the ally burned (same as the crypt-card case) while
  *paying* must keep the ally in `zone == "contested"` (not restore it to
  `"ready"`, unlike the crypt-card case, since the ally is still out of play
  while any contest persists) and only the side whose opponent's copy was
  the one yielded should restore to `"ready"` on its own next unlock phase
  (per the rulebook's "unlocked and turned face up during your next unlock
  phase, ending the contest" -- note this is a *further* unlock phase after
  the yield, not instantaneous, mirroring how `resolve_one_contest`'s own
  "yield" branch already clears the opponent's `contested_with` immediately
  but the opponent's crypt card needed no further unlocking step only
  because the 2P override already kept it `zone == "ready"` throughout).
  Whether that same one-unlock-phase-later nuance needs its own dedicated
  engine step for the ally case (since, unlike the crypt-card case, the
  surviving copy's `zone` must actually change from `"contested"` back to
  `"ready"` on that later unlock, not merely drop a flag) should be checked
  carefully against the rulebook's exact wording before building --
  `rules-engineer` scope.
- Also relevant: Shilmulo Tarot (101767, unique Equipment, OQ-10's own quick
  sweep) needs an analogous fix on the `CardAttachment` side (`engine/
  cards.py`), which has no `contested_with` tracking of its own at all --
  out of this entry's scope (no card module needs it yet) but flagged so it
  is not lost.
- Impacted code (not yet touched): `src/vtesbot/engine/phases/unlock.py`,
  `src/vtesbot/engine/allies.py` or `engine/contests.py` (an ally-side
  resolution function). Impacted cards: 47th Street Royals and the five
  other unique allies OQ-10's sweep found all need this before any of them
  can safely leave a contest once entered; `card-implementer` should treat
  this as a prerequisite (alongside OQ-10's own now-resolved detection half)
  when deciding whether to unblock any of them.
- Resolution (`rules-engineer` pass): confirmed, re-fetching live and
  cross-checking the local cache again, that this was always an engineering
  gap, not a ruling ambiguity -- the rulebook's own "Contested Cards"
  paragraph (quoted in full above) is one unified pay-1-pool-per-unlock-
  phase-or-yield mechanism for every unique card, and the 2P variant's
  "Contested crypt cards" override changes only the face-down/out-of-play
  half, only for crypt cards (re-confirmed against `data/sources/
  2p-variant/2026-10-09/variant.md`'s own title and its own aside). Built
  exactly what this entry's own "what would be needed" described, reusing
  `engine/contests.py::resolve_one_contest`'s shape rather than reinventing
  it:
  1. `src/vtesbot/engine/allies.py` gained `resolve_one_ally_contest(state,
     player, ally)`, mirroring `resolve_one_contest`'s two branches
     ("pay": `lose_pool(state, player, 1)`; "yield": burn the yielding
     ally, clear the opponent's own `contested_with`) with the one
     deliberate difference this entry flagged as needing care: because an
     ally has no 2P "stays usable" override (unlike a crypt card), *neither*
     branch restores `zone` to `"ready"` -- "pay" leaves the ally at
     `zone == "contested"` (still out of play, per `AllyInPlay`'s own
     docstring), and "yield"'s surviving opponent copy also stays at
     `zone == "contested"` even though its `contested_with` is cleared
     immediately. Also added `_find_ally_instance`, the ally-side analogue
     of `engine/contests.py::_find_instance`.
  2. The one-unlock-phase-later nuance is handled by a new, separate,
     mandatory step, `src/vtesbot/engine/phases/unlock.py::
     _unlock_own_allies(state, player)`, run once per `unlock_phase` call
     alongside (immediately after) the existing `_unlock_own_vampires` --
     *before* the optional pay-or-yield loop, not inside it. It scans the
     acting player's own allies for exactly the state `resolve_one_ally_
     contest`'s "yield" branch leaves behind on the surviving side
     (`zone == "contested"` and `contested_with is None`) and only then
     flips `zone` to `"ready"` and clears `locked`. This correctly models
     "unlocked and turned face up during your next unlock phase, ending the
     contest" as a further event on the *surviving controller's own* next
     `unlock_phase` call -- which, per 2P's alternating turns, may not run
     until after the opponent's own next turn too, since `unlock_phase` is
     only ever invoked for the currently-active player
     (`engine/phases/turn.py::play_turn`). An ally still actively contested
     (`contested_with` still set) is left untouched by this step, since it
     is instead surfaced by the pay-or-yield loop below.
  3. `_pending_effect_ids` (`engine/phases/unlock.py`) now also yields one
     `f"contest_ally:{a.instance_id}"` entry per the player's own
     currently-contested ally (`contested_with is not None`, `zone !=
     "burned"`), mirroring the existing `f"contest:{v.instance_id}"` vampire
     entries exactly; `_resolve_optional_effects_in_chosen_order` dispatches
     a `"contest_ally:"`-prefixed id to `resolve_one_ally_contest` (checked
     before the generic vampire-id branch, since both share a `:`-separated
     shape).
  Proven by `tests/rules/test_ally_contest_resolution.py`: a contested
  ally's controller is offered `"ally_contest_resolution"` (pay/yield)
  during their own `unlock_phase` call; paying costs 1 pool and leaves
  *both* copies at `zone == "contested"` (still out of play, unlike the
  crypt-card case); yielding burns the yielding ally, costs no pool, and
  leaves the surviving opponent copy's `contested_with` cleared but its
  `zone` still `"contested"` immediately afterward (not yet restored); a
  follow-up `unlock_phase` call for the *surviving* controller only then
  restores that ally to `zone == "ready"`, `locked is False`,
  `contested_with is None`, with no further decision asked of either
  player (zero pending effects remain); plus a zero-regression check that
  an uncontested ally's `zone`/`contested_with` are left untouched by
  `unlock_phase`.
  Zero-regression: the pre-existing crypt-card contest-resolution tests
  (`tests/rules/test_unlock.py`) and OQ-10's own ally-detection tests
  (`tests/rules/test_ally_contests.py`) are untouched and still pass
  unmodified. Full suite green: 190 passing (up from 185; 5 new, 0
  regressions), `ruff check`/`ruff format --check` clean.
  Deliberately **not** built, confirmed still out of scope (no card module
  needs it yet, same boundary this entry already drew): an analogous
  contest-resolution mechanism for Shilmulo Tarot (101767, unique
  Equipment) on the `CardAttachment` side (`engine/cards.py`), which still
  has no `contested_with` tracking of its own at all -- left as a
  separately-flagged future gap, not addressed here.
- Impacted code: `src/vtesbot/engine/allies.py`
  (`resolve_one_ally_contest`, `_find_ally_instance`),
  `src/vtesbot/engine/phases/unlock.py` (`_unlock_own_allies`,
  `_pending_effect_ids`, `_resolve_optional_effects_in_chosen_order`,
  `unlock_phase`). Card registration is unchanged (47th Street Royals and
  the five other unique allies OQ-10's sweep found stay `blocked` in the
  registry; this closes a prerequisite for `card-implementer`, who should
  still get a `rules-auditor` review of this change -- core engine/unlock-
  phase mechanics -- before wiring any of the six unique-ally card
  modules against it).

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

## OQ-17: No action-card entry point -- Enchant Kindred (100640) (status: resolved)

- Situation: card text (verbatim, via krcg 4.18 `VTES['Enchant Kindred'].card_text`
  and cross-checked against the live `https://api.krcg.org/card/100640`,
  2026-10-10, matching the raw snapshot `data/cards/100640.json`): "[pre] Ⓓ
  Bleed with +1 bleed.\n[PRE] +1 stealth action. Add 2 blood to a younger
  vampire in your uncontrolled region." `types == ["Action"]` (not "Action
  Modifier"); `discipline_requirement == {"type": "Mono", "disciplines":
  ["pre"]}`; `clan_requirement == []`; `cost is None`; `burn_option is
  False`; `trifle is False`. Rulings: none on file (`rulings == []`, both via
  the installed `krcg` package and the live API). Not a ruling ambiguity --
  the text is plain (see below for the one textual-convention point this
  entry deliberately does *not* block on). The block is a missing engine
  representation.
- The rulebook glossary defines the "Ⓓ" icon's referent directly:
  "**Directed Action:** An action of one Methuselah's minion that targets
  one or [more → only one in 2P] other Methuselah['s minions]"
  (`data/sources/rulebook/2026-10-09/8-glossaries.md:59`), with
  "**Undirected Action:** An action that is not directed" immediately below
  it (same file, line 197). So the basic clause ("[pre] Ⓓ Bleed with +1
  bleed") is a *directed* action -- mechanically a bleed, amount 2 instead of
  the default 1 -- and the superior clause ("+1 stealth action. Add 2 blood
  to a younger vampire in your uncontrolled region") is *undirected* (it
  names no target Methuselah at all; its own effect only ever touches the
  acting player's own uncontrolled region). Both already collapse cleanly to
  the existing single-opponent block-attempt model `engine/action.py`'s own
  module docstring documents for the 2P duel (not OQ-1 -- that structural
  collapse is already settled), so neither clause raises a *fresh*
  prey/predator question.
- What is blocked: `types == ["Action"]` means this card itself constitutes
  the acting vampire's one minion action for the turn (Rulebook SS2 Card
  Types; distinct from an "Action Modifier," which only ever decorates an
  *already-chosen* default action). The only place a card can inject a new,
  self-contained minion action alongside the built-in "Bleed"/"Hunt" choices
  is `engine/phases/minion.py::_choose_and_perform_action`'s top-level
  `action_choice` decision, and the only hook that call site currently
  splices options from is `RECRUIT_ALLY_PLAY_HOOK` (`"recruit_ally_play"`,
  OQ-12) -- which is Ally-specific (its `apply()` contract returns an
  `engine/allies.py::RecruitAllySpec`, consumed only by
  `_perform_recruit_ally`, not a bleed/undirected-action shape at all).
  There is no generic "this library card is itself an alternate minion
  action" hook: confirmed by reading every entry in
  `src/vtesbot/cards/registry.py`'s `Hook` enum (both the "wired this pass"
  group and the "named for classification, no wiring yet" group) -- none of
  them represent "a played Action card supplies its own base stealth,
  directed/undirected shape, and resolve() to `perform_minion_action`,
  spliced into the same top-level choice `_choose_and_perform_action`
  offers." Implementing either clause today would mean either (a) misusing
  `BLEED_AMOUNT_MODIFIER_HOOK`/`BLEED_AMOUNT_FIXED_MODIFIER_HOOK` to fake an
  "Action" card as if it were an Action Modifier layered onto a *separately,
  already-chosen* free default Bleed -- wrong card type, and for the basic
  clause specifically it would also wrongly let a player bleed for free (no
  card played, no hand cost) and *additionally* play Enchant Kindred as a
  bonus on top, when the real card text is itself the only bleed this
  vampire's action performs -- or (b) inventing a new top-level choice/call
  site inside the card module by reaching into `engine/phases/minion.py`
  directly, which is exactly the "hack around a missing engine mechanism
  inside the card module" CLAUDE.md forbids. Neither clause can be
  correctly wired without new, generic engine-side scope; per CLAUDE.md
  §6's "implemented only when ... fully tested" bar (no partial
  implementation of only one clause), the whole card is blocked.
- What would be needed (`rules-engineer` scope, `engine/phases/minion.py`
  and `engine/action.py`, mirroring the existing `recruit_ally_play`
  pattern but generalized beyond Allies): a new hook (e.g.
  `"action_card_play"`) offered at `_choose_and_perform_action`'s top level
  alongside `ACTION_BLEED`/`ACTION_HUNT`/the recruit-ally options, whose
  provider contract lets a registering card module supply (1) the base
  stealth for its own action, (2) whether it is directed (at the single 2P
  opponent) or undirected, (3) a `resolve(pending)` callback run by
  `perform_minion_action` exactly like `_perform_bleed`/`_perform_hunt`'s
  own closures, and (4) how/when its card is consumed from hand (for a plain
  one-shot "Action" card such as this one, immediately via
  `vtesbot.cards._shared.play_from_hand` at the moment the choice is made --
  unlike Recruit Ally's Ally card, an "Action" card's own text has no
  "put into play" destination that depends on the later block outcome, so
  `play_from_hand_pending`'s two-destination dance is not needed here,
  though a future, different "Action" card might need it; the new hook's
  contract should accommodate both). Once that hook/call site exists,
  Enchant Kindred's own two providers become straightforward: the basic
  clause's `resolve()` mirrors `_perform_bleed`'s, with `amount = 1 + 1`
  baked in; the superior clause's `resolve()` is undirected and, once
  unblocked, raises a new `Decision` (the existing `Decision`/`Choice`
  machinery already supports an arbitrary "pick one of your own eligible
  minions" choice with no further engine change -- only the top-level
  action-card hook itself is the actual gap) letting the acting player pick
  one of their own `zone == "uncontrolled"` vampires, then calls the
  already-existing `engine/damage.py::add_blood(state, chosen, 2)`.
- Textual-convention point, deliberately *not* blocking (noted for whoever
  unblocks this card next): the superior clause's "a younger vampire" names
  no explicit comparison target ("younger than *what*"). The rulebook
  glossary states capacity "is also a relative measure of the vampire's age"
  (`data/sources/rulebook/2026-10-09/8-glossaries.md:47-48`), and a broad
  cross-section of other printed card texts using the identical unqualified
  "younger vampire"/"a younger vampire" phrasing (e.g. Danny Larkshill:
  "gets +1 strength in combat with a younger vampire"; Apolonia Czarnecki:
  "can steal 1 blood from a younger vampire as a Ⓓ action" -- both checked
  live via `krcg.load()`, 2026-10-10) are uniformly read, by the same
  unqualified-comparative convention, as relative to the one vampire the
  ability belongs to (the acting/printed-ability vampire), not some other
  unnamed reference. This is corroborating pattern evidence, not itself an
  official ruling for *this* card, so it is flagged rather than silently
  assumed -- but it does not change this entry's blocking reason (the
  missing engine hook blocks implementation regardless of how "younger" is
  ultimately read), so it is not filed as its own, separate Open Question.
  Confirmed by the project owner (2026-10-10): read "a younger vampire" in
  the superior clause as younger than the acting vampire (the vampire using
  the [PRE] ability), consistent with the convention above. Whoever
  unblocks this card once OQ-17's engine hook exists should implement the
  superior clause's target filter against that reading directly, with no
  further ruling lookup needed on this specific point.
- Impacted code (at the time this was opened): none yet (no generic
  "Action"-card entry point exists to extend). Impacted cards: Enchant
  Kindred (registered `blocked`, reason `OQ-17`); any future 2P-legal card
  of `types == ["Action"]` (as opposed to "Action Modifier") would hit the
  same gap.
- Resolution (`rules-engineer` pass): built the generic "Action"-card entry
  point this entry's own "What would be needed" paragraph specified, mirroring
  (and generalizing beyond Allies) `RECRUIT_ALLY_PLAY_HOOK`/`RecruitAllySpec`'s
  own OQ-12 pattern.
  - `src/vtesbot/engine/phases/minion.py`: new `ACTION_CARD_PLAY_HOOK =
    "action_card_play"` (`HookOption`-based, same shape as
    `RECRUIT_ALLY_PLAY_HOOK`), a new frozen `ActionCardSpec` dataclass (a
    registered provider's `apply(state)` must return one), and a new
    `_perform_action_card` function that runs `spec.resolve`/`spec.
    on_blocked` through `perform_minion_action` under `spec.action`.
    `_choose_and_perform_action` now also offers `hooks.offer(ACTION_
    CARD_PLAY_HOOK, ...)` options at its top-level `action_choice`
    decision, alongside `ACTION_BLEED`/`ACTION_HUNT`/the recruit-ally
    options, threading the same `vampire=vampire.instance_id` context
    OQ-13 already required for `RECRUIT_ALLY_PLAY_HOOK`.
  - `ActionCardSpec`'s contract (`base_stealth: int`, `directed: bool`,
    `resolve: Callable[[dict[str, Any]], None]`, `on_blocked:
    Callable[[dict[str, Any]], None] | None = None`, `action: str =
    ACTION_ACTION_CARD`) deliberately does not hard-code *how* the
    provider's own card leaves hand: a plain one-shot Action card (e.g.
    Enchant Kindred) consumes it immediately via `vtesbot.cards._shared.
    play_from_hand` inside its own `apply(state)`, since both of Rulebook
    SS4 "Resolve the Action"'s branches end the same way (ash heap) for
    such a card; a future Action card whose own placement *does* depend on
    the later block outcome can instead use `vtesbot.cards._shared.
    play_from_hand_pending` and supply its own `on_blocked`, exactly like
    `RecruitAllySpec` already does -- proven generically (not just
    asserted, and with two genuinely distinct destinations rather than both
    branches landing on the ash heap) by `tests/rules/
    test_action_card_play.py::test_action_card_play_supports_the_two_
    destination_dance_generically`.
  - Rules-auditor finding (fixed in the same pass, before this entry was
    marked resolved): the first draft of this hook tagged *every*
    `ActionCardSpec` with the fixed `ACTION_ACTION_CARD` discriminator,
    regardless of what the clause's own card text mechanically is. Enchant
    Kindred's own basic clause prints the word "Bleed" ("[pre] Ⓓ Bleed with
    +1 bleed" -- confirmed directly via krcg, CLAUDE.md SS2 card-text
    precedence, no ruling needed), so tagging it `"action_card"` instead of
    `"bleed"` would have silently and wrongly suppressed an existing
    bleed-gated provider sharing the same hook window (e.g. `cards/
    bonding.py`'s superior clause, gated on `context.get("action") ==
    ACTION_BLEED`) once Enchant Kindred is wired up -- exactly the "never
    mis-resolves a card" bar CLAUDE.md sets. Fix: `ActionCardSpec` gained
    an `action: str = ACTION_ACTION_CARD` field so a provider can declare
    the real mechanical action identity its own clause matches (defaulting
    to the generic fallback for a clause that is genuinely sui generis,
    e.g. Enchant Kindred's own superior clause, "Add 2 blood to a younger
    vampire," which is not textually a bleed/hunt/etc.); `_perform_action_
    card` forwards `spec.action` instead of the fixed constant. Proven by
    `tests/rules/test_action_card_play.py::test_action_card_play_can_
    declare_itself_a_real_bleed_so_bonding_still_fires`, which registers
    `cards/bonding.py`'s own real, unmodified `"stealth_modifier"` provider
    directly and shows its superior clause is correctly *not* offered when
    `action` is left at the generic default, and correctly *is* offered
    once a fake provider declares `action=ACTION_BLEED` for its clause.
  - `src/vtesbot/engine/action.py`: added the `ACTION_ACTION_CARD = "action_
    card"` discriminator (OQ-9's family) and a new `directed: bool | None =
    None` parameter threaded through `_duel_stealth_intercept`/
    `attempt_block`/`perform_minion_action` into both the `"block_attempt"`
    decision's own context and the stealth/intercept hook context (mirroring
    how `action` is already threaded) -- the Rulebook glossary's "Directed
    Action"/"Undirected Action" distinction this entry's own "What is
    blocked" paragraph already confirmed collapses to the same single-
    opponent block-attempt call in 2P, so this changes no block-attempt
    mechanics; it exists purely so a provider can supply, and a future
    hook/decision consumer (or the replay log) can read, which of the two
    an action-card play actually is. `_perform_bleed`/`_perform_hunt`/
    `_perform_recruit_ally` were updated to pass their own already-sourced
    `directed=True`/`False` values for consistency (no behaviour change: no
    existing hook provider reads this key).
  - `src/vtesbot/cards/registry.py`: moved `Hook.ACTION_CARD_PLAY` from the
    "named for classification, no wiring yet" group into the "wired this
    pass" group, now that `ACTION_CARD_PLAY_HOOK` has a real call site.
  - Tests: `tests/rules/test_action_card_play.py` (new) -- zero-regression
    (not offered without a registered provider, or without a matching hand
    card), offered-and-succeeds (immediate consumption, `resolve` fires),
    blocked (card already consumed, `resolve` does not fire, combat still
    happens), the `action`/`directed` discriminators threaded into the
    block-attempt hook context, the OQ-13-style `vampire` context binding,
    and the two-destination-dance generality case above.
  - Not done by this pass, deliberately: Enchant Kindred's own card module
    (registering against `ACTION_CARD_PLAY_HOOK` and flipping its own
    registry entry from `blocked` to `implemented`) -- a separate
    `card-implementer` pass, per this entry's own "Impacted cards" line
    above (left unchanged).
- `card-implementer` follow-up (Enchant Kindred, krcg 100640, now wired):
  re-verified the card text/rulings/legality against both the installed
  `krcg` package's own cached snapshot and a fresh live fetch of
  `https://api.krcg.org/card/100640` (2026-10-10) -- unchanged, matching
  `data/cards/100640.json` byte-for-byte. `src/vtesbot/cards/
  enchant_kindred.py` now registers two `ACTION_CARD_PLAY_HOOK` providers
  (mirroring the "basic vs superior, two providers for one physical card"
  shape already used by `bonding.py`): the basic clause ("[pre] Ⓓ Bleed
  with +1 bleed") declares `ActionCardSpec.action=ACTION_BLEED` (the
  rules-auditor-fixed requirement this entry's own resolution flagged, since
  its own text literally prints "Bleed") and its `resolve()` mirrors
  `_perform_bleed`'s own closure byte-for-byte with the base amount
  hardcoded to 2; the superior clause ("+1 stealth action. Add 2 blood to a
  younger vampire in your uncontrolled region") is undirected, bakes in its
  own printed "+1 stealth" as `base_stealth=1`, and -- confirming this
  entry's own "what would be needed" paragraph was correct, no further
  engine change was needed -- raises a plain `Decision`/`Choice` directly
  inside its own `resolve()` to let the acting player pick among their own
  `zone == "uncontrolled"` vampires strictly lower in printed capacity (the
  project owner's confirmed reading of "younger," per this entry's own
  textual-convention note above), clamped to only those with room for at
  least 1 of the printed 2 blood (`engine/attachments.py::
  effective_capacity`, OQ-8), then calls `engine/damage.py::add_blood`;
  with exactly one eligible target the amount is applied with no decision
  raised at all (mirrors `engine/phases/unlock.py::
  _resolve_optional_effects_in_chosen_order`'s own "only when needed"
  len-1-auto-apply convention), confirming the "no further engine change
  needed" claim end-to-end rather than merely asserting it. Both clauses
  gate on basic/superior Presence (`"pre"`/`"PRE"`) the same way `bonding.py`
  gates on Dominate. Proven by `tests/cards/test_enchant_kindred.py` (18
  tests, one per clause/qualifier plus a worked integration proof that the
  basic clause's `ACTION_BLEED` tagging lets Bonding's own real, unmodified
  superior clause still fire during the same window, mirroring `tests/
  rules/test_action_card_play.py::test_action_card_play_can_declare_itself_a_
  real_bleed_so_bonding_still_fires`). Full suite green (238 passed, up from
  220; zero regressions), `ruff check`/`ruff format --check` clean. No
  engine code touched by this pass -- the hook this entry built already
  covered everything needed.

## OQ-18: No sect, no dodge/extra strike -- Dust Up (100597) (status: resolved)

- Resolution (2026-10-10): both gaps closed and independently confirmed by a
  final `rules-auditor` pass (full suite 259 passed, `ruff`/`pymarkdown`
  clean): Gap 1 (vampire sect, `Sect`/`CryptCard.sect`/`derive_sect` in
  `src/vtesbot/engine/cards.py`) and Gap 2 (dodge + same-round additional
  strike in `src/vtesbot/engine/combat.py`, including the dodge-proof
  `StrikeDamage.ignore_dodge` override needed for Dust Up's own `[ani]`
  clause). The auditor hand-traced `_resolve_strike_pair`'s arithmetic
  directly (not just the tests) and confirmed it correctly lets a
  dodge-proof strike deal damage through a dodge while leaving the dodging
  combatant's own simultaneous counter-strike unaffected. Dust Up itself is
  ready for a `card-implementer` pass covering all three clauses
  (`[ani]`/`[cel]`/`[pot]`) plus the "Requires an Anarch" sect gate; see the
  Gap 1/Gap 2 sub-notes below for the full build history and sourcing.

- Situation: card text (verbatim, re-verified via the installed `krcg` 4.18
  package's own `VTES["Dust Up"].to_json()` and cross-checked live against
  `https://api.krcg.org/card/100597`, 2026-10-10, saved to
  `data/cards/100597.json`): "Requires an Anarch.\n[ani] Strike: hand strike
  at +1 damage. This strike cannot be dodged.\n[cel] Strike: dodge, with 1
  additional strike (limited).\n[pot] Strike: hand strike at +2 damage."
  `types == ["Combat"]`; live API `discipline_requirement == {"type":
  "Choice", "disciplines": ["ani", "cel", "pot"]}` (any *one* of the three,
  all lowercase -- basic/inferior level satisfies the requirement to play
  the card at all; confirmed by the installed package's own `multidisc ==
  True` and lowercase-only `disciplines == ["ani", "cel", "pot"]`, no
  uppercase/superior variant printed anywhere on the card); `clan_requirement
  == []`; `path_requirement == []`; `cost is None`; `burn_option is False`;
  `trifle is False`. Confirmed on the active 2P allowed list
  (`data/formats/2p/2026-10-03.json`, krcg id 100597) and in the suggested
  2P decklist `data/decks/vekn-2p/brujah.json` (6 copies; not also present in
  `toreador.json`/`ventrue.json`, correcting the task's framing that the 6
  copies were spread across all three -- all 6 are in the Brujah list alone).
  Rulings (verbatim, via krcg, both the installed package and the live API
  agree):
  - "[ani] [pot] Additional damage inherits all of the properties of the
    base damage." [TOM 19960225]
  - "[cel] The additional strike is not optional: you cannot play it for the
    dodge only if you already played it for a (limited) additional strike
    this round." [ANK 20220204]
  - "When played, a multi-Disciplines card counts as requiring the
    Discipline(s) being used. In the hand, library, or ash heap, the card is
    considered to require any and/or all Disciplines listed on it." [LSJ
    20011204-3] [PIB 20130704]
  - "[ani] Does not prevent the opponent from dodging, the dodge just has no
    effect." [LSJ 20030902-2] [LSJ 20060808-1]
  Not a ruling ambiguity -- the text and rulings are plain and mutually
  consistent. The block is two independent missing-engine-representation
  gaps, either one alone sufficient to block the whole card (CLAUDE.md §6: a
  card is implemented only when *all* of its text is tested; no partial
  implementation of only the clauses one gap happens not to touch).
- Gap 1 -- "Requires an Anarch" (blocks the card's playability entirely,
  regardless of discipline clause): sect (Camarilla / Anarch / Sabbat /
  Independent / Laibon) is a genuine, persistent, rules-significant per-
  vampire trait, not flavour text -- re-fetched the Rulebook live
  (<https://www.vekn.net/rulebook/6-vampire-sects>, cross-checked against the
  local cache `data/sources/rulebook/2026-10-09/6-vampire-sects.md`), quoted
  verbatim: "A vampire always belongs to one and only one sect." / "Some
  cards can only be played by Anarch vampires." / "An untitled non-Anarch
  vampire can become an Anarch as a +1 stealth undirected action that costs
  2 blood, or 1 blood if the controller controls at least 1 other ready
  Anarch. A vampire can also be made an Anarch by certain card effects.
  Becoming Anarch constitutes a change of sect." `src/vtesbot/engine/
  cards.py::CryptCard` (the engine's own vampire-identity dataclass) has no
  `sect` field at all -- only `krcg_id`, `name`, `capacity`, `group`,
  `clan`, `title`, `disciplines`, each explicitly documented as "plain
  printed stats"; sect is conspicuously absent from that list, and no other
  engine module (`state.py`, `attachments.py`, `setup.py`) carries it either
  (confirmed by grep across `engine/` for "sect"/"Anarch": zero hits besides
  an unrelated comment naming "become Anarch" as future out-of-scope minion
  action text in `engine/phases/minion.py`). Nor does krcg itself expose a
  structured sect field to read from: neither the installed package's
  `Card.to_json()` (sampled `VTES["Victoria Ash"]`, `VTES["Jeremy
  MacNeil"]` -- no `sect` key in either) nor the live API's own structured
  requirement fields (`clan_requirement`/`discipline_requirement`/
  `path_requirement`, present on this very card and on Enchant Kindred's
  cached snapshot, `data/cards/100640.json`) have a `sect_requirement` or
  equivalent counterpart. Sect is only ever embedded as free text at the
  very start of a vampire's own printed `card_text` (e.g. Jeremy MacNeil:
  `"Camarilla."`; a live sample of vampires matching `"Anarch"` in their own
  text: Aluc Romas de Leon `"Anarch."`, Anita Wainwright `"Anarch."`, Ariane
  `"Anarch: Ariane gets -1 stealth during undirected actions."`, several
  "Anarch Baron of \<city\>" titled vampires) -- a free-text convention, not
  a parseable field, and reliably classifying it (distinguishing a sect
  preamble from the rest of a vampire's own printed ability text, handling
  vampires with no sect preamble at all = Independent) is itself a non-
  trivial text-classification task that must be solved once, generically, in
  the engine's own vampire-identity model -- not invented ad hoc inside this
  one card's module (CLAUDE.md "no hacking around a missing engine
  mechanism"). Separately, milestone 1's deck-import pipeline does not exist
  yet at all (confirmed: no `CryptCard(` construction site anywhere in
  production code outside `engine/cards.py`'s own definition, `engine/
  state.py`, `engine/attachments.py`, `engine/setup.py`, and scenario-test
  helpers), so there is currently no path, even a manual one, by which a
  real vampire's sect would reach a `CryptCard` instance in the first place.
- Gap 2 -- the `[cel]` clause ("dodge, with 1 additional strike (limited)")
  needs two further combat mechanics that do not exist anywhere in
  `engine/combat.py`, independent of Gap 1: re-read the module in full
  (2026-10-10) and confirmed its own docstring is explicit about this scope
  boundary: "Maneuvers, ranged strikes, and additional strikes remain out of
  scope this pass (no combat card in the current pool's classification
  needs them *without* also needing the maneuver/range mechanic itself...)."
  Concretely: (a) **no dodge mechanic** -- `_ask_strike`'s only two built-in
  choices are `"hand_strike"` and `"no_strike"`; "no_strike" means "I do not
  attack this round" but does *not* prevent the opponent's simultaneous
  strike from damaging me (`run_combat`'s "Simultaneous" comment, both
  `damage_to_blocking`/`damage_to_acting` are applied unconditionally from
  each side's own independently-chosen strike). A genuine "dodge" (avoid
  taking damage from the opponent's strike this round, per the [ani] ruling
  above confirming dodge is a real, distinct choice the opponent can still
  make against a [ani] strike, "the dodge just has no effect" implying it
  normally *does* have an effect) has no engine representation at all. (b)
  **no same-round additional strike** -- `run_combat`'s round loop calls
  `_ask_strike`/`_strike_damage` exactly once per combatant per round; there
  is no mechanism for a combatant to resolve a second strike within the same
  round (confirmed: grep across `engine/` for "additional strike"/"extra
  strike"/"multiple strike" returns only this module's own docstring
  sentence naming the gap). `COMBAT_STRIKE_OPTION_HOOK`'s own contract
  (`apply(state) -> int`, consumed by `_strike_damage` as "the damage this
  strike-substitute inflicts," module docstring: "a card-granted strike
  option's `apply(state)` must return the damage it inflicts, so it can
  fully stand in for a hand strike") can only ever express a single,
  ordinary damage-dealing hand-strike substitute -- it has no way to signal
  "no damage to me this round regardless of what the opponent strikes with"
  or "resolve a second, independent strike within this same round." So even
  a hypothetical sect-agnostic version of this card could only ever
  implement its `[ani]`/`[pot]` clauses through this already-wired hook; its
  `[cel]` clause cannot be implemented against the engine as it stands
  today, a second, independent block.
- **Gap 2 resolved (2026-10-10, `rules-engineer`).** Re-fetched live
  <https://www.vekn.net/rulebook/4-detailed-turn-sequence> and cross-checked
  against the local cache `data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md` (verbatim match, no drift) before building
  anything. `engine/combat.py` now wires two further hooks, generalized the
  same way `COMBAT_STRIKE_OPTION_HOOK`/`COMBAT_STRENGTH_MODIFIER_HOOK`
  already generalize "a card grants an alternate strike"/"a card grants a
  passive strength bonus" -- not Dust-Up-specific, since any future dodge-
  or extra-strike-granting combat card hits the identical gap:
  - `COMBAT_DODGE_OPTION_HOOK` (`"combat_dodge_option"`, `registry.Hook.
    COMBAT_DODGE_OPTION`): offered alongside `COMBAT_STRIKE_OPTION_HOOK` at
    the strike step (`_ask_strike`). Per Rulebook SS4 Combat > Choose
    Strike, dodge is only ever "from any other card providing this minion a
    strike," never a base/default option every vampire has -- confirmed no
    built-in dodge choice is offered without a registered provider. Per
    Strike Effects > Dodge ("A dodge strike deals no damage, but it
    protects the dodging minion ... from the effects of the opposing
    strike"), the engine enforces both halves directly in
    `_resolve_one_strike`/`_resolve_strike_pair` (not via a provider's
    `apply` return value): choosing it always deals 0 damage from that
    strike and always zeroes whatever damage the opponent's *simultaneous*
    strike this round would otherwise deal to the dodging combatant.
  - `COMBAT_ADDITIONAL_STRIKE_HOOK` (`"combat_additional_strike"`,
    `registry.Hook.COMBAT_ADDITIONAL_STRIKE`): offered once per combatant
    after the normal strike pair (and after each additional-strike pair,
    acting combatant asked first) via `_ask_additional_strike`; using one
    re-enters the *full* strike-choice machinery (`_ask_strike`, including
    `COMBAT_STRIKE_OPTION_HOOK`/`COMBAT_DODGE_OPTION_HOOK`) for that
    combatant's additional strike, exactly like a normal strike -- an
    additional strike is never a fixed/hardcoded hand strike (per Rulebook
    SS4 Combat > Additional Strikes: "another choose strike step ... in
    which only the minions with additional strikes may play strike cards";
    Choose Strike places no narrower restriction on what an additional
    strike can be chosen from). A combatant with no available/unused grant
    does not strike in that pair at all (not even offered "no_strike"),
    matching "only the minions with additional strikes may play strike
    cards." The loop repeats "as necessary" while either combatant still
    has an unused grant, reproducing the Wauneka/Flávio Gonçalves worked
    example's shape (one side runs out before the other).
  **Amendment (2026-10-10, `rules-auditor` finding, fixed same pass):** the
  first version of this fix enforced dodge *unconditionally* -- any dodge
  always zeroed the opponent's damage, with no way for a specific strike to
  override that, even though the Golden Rule for Cards (CLAUDE.md SS2 /
  Rulebook SS3: "whenever the cards contradict the rules, the cards take
  precedence") lets a strike's own printed text do exactly that. Dust Up's
  own `[ani]` clause ("This strike cannot be dodged") is the sourced
  example, confirmed by its ruling: "[ani] Does not prevent the opponent
  from dodging, the dodge just has no effect." [LSJ 20030902-2] [LSJ
  20060808-1] -- the opponent may still *choose* to dodge, but that dodge
  has zero effect against this one, specifically-flagged strike (the
  dodging combatant's own simultaneous strike against the attacker is
  unaffected either way). Added `combat.StrikeDamage` (a small frozen
  dataclass, `amount: int, ignore_dodge: bool = False`): a
  `COMBAT_STRIKE_OPTION_HOOK` provider's `apply(state)` may return this
  instead of a plain `int` to flag its strike dodge-proof; `_resolve_one_
  strike`/`_resolve_strike_pair` now track an `ignore_opponent_dodge` flag
  per strike and only zero a dodging combatant's incoming damage when the
  attacking strike did *not* set it. Hand strikes, `no_strike`, and dodge
  itself never carry this (only a card-granted strike option plausibly
  needs it). Documented as a known future gap (not built, no current card
  needs it): dodge here still only nullifies numeric damage, not a future
  non-damage strike effect (e.g. a Steal Blood-style strike) -- Strike
  Effects > Dodge protects from "effects" more broadly than just damage.
  Scenario tests: `tests/rules/test_combat_dodge_and_additional_strike.py`
  (5 tests) -- dodge nullifying the opponent's simultaneous strike; a
  dodge-proof strike still damaging a dodging opponent (the amendment
  above); no dodge choice offered without a provider (regression guard); an
  additional strike resolving via a card-granted `combat_strike_option`
  rather than a hand strike (proving the full choice surface, not a
  shortcut); the defender not being asked a second `strike_choice` when it
  has no grant. All use fake, test-only providers registered/unregistered
  within the test (`docs/DECISIONS.md` D-5), via the named hook constants
  (not raw hook-name strings, per OQ-9's same typo-risk fix), independent of
  Dust Up's own wording -- per the [LSJ 20030902-2]/[LSJ 20060808-1] rulings
  quoted above, dodge is its own real, generic mechanic, not something that
  should only exist in service of one card. `cards/dust_up.py` is left
  untouched (still `blocked` on Gap 1; wiring its own `[cel]` clause against
  these two new hooks is a future `card-implementer` pass once Gap 1 also
  closes).
- Gap 1 remained outstanding at the time Gap 2 (above) was resolved --
  see the separate `rules-engineer` pass's own "Gap 1 update" note below
  (working in parallel on `engine/cards.py` sect modeling, not this pass's
  scope) for its status. Gap 1 blocks the card outright regardless of which
  discipline clause a controlling vampire would use, independent of Gap 2's
  resolution above -- so Dust Up itself remains `blocked` until Gap 1 is
  also resolved (per whichever of the two notes below is current) and a
  future `card-implementer` pass wires its `[ani]`/`[cel]`/`[pot]` clauses
  against both passes' results.
- Impacted code: `src/vtesbot/engine/cards.py` (`CryptCard`), `src/vtesbot/
  engine/combat.py`. No deck-import pipeline yet exists to extend for Gap 1.
  Impacted cards (at the time this was opened): Dust Up (registered
  `blocked`, reason `OQ-18`; now `implemented`, see the `card-implementer`
  note at the end of this entry); any future
  2P-legal card gated on a vampire's sect ("Requires a/an \<Sect\>",
  "Camarilla only," a Sabbat-only effect, etc.) would hit Gap 1; any future
  card granting a dodge or a same-round additional strike would hit Gap 2.
  Not yet swept (unlike OQ-10's explicit "quick sweep" of the pool for
  similarly-shaped cards): whether any other 2P-legal card has its own
  sect requirement or grants a dodge/additional strike -- left for a future
  pass, same "no guessing ahead of a sourced need" boundary this entry
  itself is opened under.
- **Gap 1 update (2026-10-10, `rules-engineer`): resolved.** Re-fetched
  Rulebook SS6 "Vampire Sects" <https://www.vekn.net/rulebook/6-vampire-sects>
  live (matches the local cache's `dateModified`, confirming Camarilla,
  Anarch, Sabbat, Independent) and, since SS6 alone does not mention Laibon,
  also checked Rulebook SS7 "Legacy Sets" > "Other Vampire Sects"
  <https://www.vekn.net/rulebook/7-legacy-sets> (also live, matching cache),
  which documents Laibon as the fifth sect verbatim: "Only Laibon can hold
  the laibon titles kholo and magaji." -- confirming the five sects named in
  this entry's own "what would be needed" list, just split across two
  Rulebook sections rather than one. Built:
  1. `Sect` (`StrEnum`, `src/vtesbot/engine/cards.py`): `CAMARILLA`,
     `ANARCH`, `SABBAT`, `INDEPENDENT`, `LAIBON`.
  2. `CryptCard.sect: Sect | None = None` (same file) -- a new, optional
     field alongside the dataclass's existing `clan`/`title`/`disciplines`
     "plain printed stats" fields, documented the same way. Defaults to
     `None` ("not modeled for this instance," e.g. a synthetic test
     vampire, an Imbued, or a real vampire not yet run through
     `derive_sect`), never to a guessed `Sect` member; a future card
     gating on sect must treat `None` as "does not qualify."
  3. `derive_sect(card_text: str) -> Sect` (same file): the generic,
     reusable classifier this entry called for, instead of ad hoc per-card
     logic. krcg has no structured sect field (confirmed again on the
     installed krcg 5.14 package, both `Card.to_json()` and the live API's
     requirement fields), so sect is derived from the free-text preamble at
     the very start of a vampire's own printed `card_text`. Checked against
     *every* crypt card in the installed krcg 5.14 dataset (`krcg.load()`),
     not just a hand sample: all 1765 vampire printings (Imbued excluded --
     see below) match a single regex, `^(?:Advanced,\s*)?(Camarilla|Anarch|
     Sabbat|Independent|Laibon)\b`, 100% hit rate, zero manual overrides
     needed. This also corrects an assumption in this entry's own "Gap 1"
     write-up above: there is currently no vampire with *no* sect preamble
     at all -- Independent vampires are not identified by the absence of a
     preamble, their own printed text literally starts with "Independent."
     (374 of the 1765 do). `derive_sect` still refuses to guess: text that
     does not match the regex (a future printing with a malformed/omitted
     preamble, or an Imbued's own text, which never carries a sect preamble
     since Imbued are not vampires and have no sect) raises
     `UnresolvedRulingError("OQ-18", ...)` rather than defaulting to
     Independent.
  4. Deliberately **not** built (confirmed still out of scope for unblocking
     Dust Up, which only reads an existing sect via "Requires an Anarch," a
     static playability gate, not an effect that grants one): Rulebook SS6's
     "become Anarch" undirected minion action, and the real krcg-to-
     `CryptCard` deck-import pipeline itself (still doesn't exist --
     unchanged from this entry's own finding above). `derive_sect` is built
     as a standalone, tested unit specifically so that pipeline has a
     ready-made sect-derivation function to call once it exists; this pass
     does not claim deck import works end-to-end.
  Tests: `tests/rules/test_sect.py` (new) -- `Sect`'s five members;
  `CryptCard.sect` defaults to `None` and can carry a `Sect`;
  `derive_sect` against real, verbatim krcg card text for all five sects
  (including OQ-18's own three named Anarch examples, Aluc Romas de Leon,
  Anita Wainwright, Ariane, plus an "Advanced," printing and a title-
  qualifier case), the Imbued no-preamble case, and the generic
  malformed/empty-text case, all raising `UnresolvedRulingError`. Full
  suite green (254 passed; the two combat-file tests concurrently in
  progress under Gap 2 are out of this pass's scope), `ruff check`/`ruff
  format --check` clean.
  **This resolves Gap 1 only.** Gap 2 (the `[cel]` clause's dodge/same-
  round-additional-strike mechanics in `engine/combat.py`) was handled
  separately, in parallel, by a second `rules-engineer` pass -- see its own
  "Gap 2 resolved" note earlier in this entry, which reports it resolved as
  well. Dust Up itself still remains `blocked`: neither pass wired
  `cards/dust_up.py` itself against the newly-available sect field or
  combat hooks (both left that to a future `card-implementer` pass, by
  design -- CLAUDE.md §6's all-or-nothing bar means the card is not
  "implemented" merely because its blocking gaps are closed). This entry's
  overall header status is left as **open** by both passes deliberately
  (per each pass's own instructions not to unilaterally mark the whole
  entry resolved) pending a single reconciling pass (e.g. `rules-auditor`
  or the user) confirming both gap-resolution notes together, then flipping
  the header and handing the card to `card-implementer`.
- **Note on this entry's own header vs. its last paragraph (2026-10-10,
  `card-implementer`):** the header above already read "(status:
  resolved)" by the time this pass started (per the task that assigned this
  pass: "OQ-18 ... is now fully resolved and re-audited ... status:
  resolved, confirmed closed"), even though the immediately preceding
  paragraph still says the header was "left as open ... pending a single
  reconciling pass." Not re-litigated or second-guessed here (this pass
  did not itself re-audit Gap 1/Gap 2's own resolutions, only built on top
  of them, exactly as both gap-resolution notes above anticipated); flagged
  so a future reader does not mistake the stale "left as open" sentence for
  this entry's current status.
- **`card-implementer` pass (2026-10-10): Dust Up implemented**
  (`src/vtesbot/cards/dust_up.py`, `tests/cards/test_dust_up.py`, 18 tests).
  Re-verified the card text/rulings against the live krcg API and the
  cached `data/cards/100597.json` snapshot -- unchanged, matching this
  entry's own earlier quotes. All three clauses wired: `[ani]`/`[pot]` as
  `"combat_strike_option"` providers (base hand-strike damage, i.e.
  `HAND_STRIKE_STRENGTH` plus any live `"combat_strength_modifier"`
  contribution, so the "additional damage inherits all of the properties of
  the base damage" ruling holds structurally, not by coincidence; `[ani]`
  additionally flags `StrikeDamage(ignore_dodge=True)`); `[cel]` as a paired
  `"combat_dodge_option"` (the dodge, plus recording an additional-strike
  grant) and `"combat_additional_strike"` (claiming that grant) provider.
  "Requires an Anarch" gates all three clauses via `vampire.card.sect is
  Sect.ANARCH` (treating `None` as "does not qualify," never guessing a
  default sect, per `CryptCard`'s own docstring).
  One deliberate, documented granularity simplification, flagged here rather
  than guessed at silently: `engine/combat.py`'s three combat hooks carry no
  round-boundary (or even combat-boundary) signal in their context (unlike
  `pending`, the per-minion-action scratch container OQ-11 built for bleed
  actions) -- re-confirmed by re-reading `_ask_strike`/`_resolve_strike_
  pair`/`_ask_additional_strike`/`run_combat` in full before concluding this,
  not assumed. Building one would be genuine new `engine/combat.py` scope
  (CLAUDE.md "No engine patches ... hand off to rules-engineer"), out of
  bounds for this pass. So the `[cel]` clause's "(limited)" restriction
  ("you cannot play it for the dodge only if you already played it for a
  (limited) additional strike this round" [ANK 20220204]) is enforced at
  "once per vampire instance, for as long as that instance exists" (in
  practice, once per game) granularity instead of precisely "once per
  round" -- strictly *more* restrictive than the sourced ruling, never less:
  it can never produce the rules-forbidden outcome (re-granting an
  additional strike, or replaying `[cel]` for the dodge only, within the
  same round), only the safe-direction cost of also disallowing a later,
  separate, legitimate replay (a different physical copy, in a later round
  of the same combat, or an entirely later combat) that the rules would in
  fact allow. Tracked card-module-side only (`dust_up.py::_cel_book`, keyed
  by `id(vampire)` with a `weakref.finalize` cleanup callback to avoid any
  cross-test/cross-game id-reuse leak -- `VampireInPlay` itself is
  unhashable, per its own plain `@dataclass` decorator with no
  `frozen=True`/`unsafe_hash=True`, so it cannot be used as a `dict`/
  `WeakKeyDictionary` key directly); no `engine/` file was touched. Flagged
  as a candidate for a future `rules-engineer` pass (a round-scoped scratch
  container threaded through `run_combat`'s three hook contexts, mirroring
  `pending`'s role for minion actions) if exact per-round fidelity is ever
  wanted; no test in `tests/cards/test_dust_up.py` exercises or claims
  correct round-2 re-availability, only the same-round restriction the
  ruling actually describes. Full suite green (277 passed, up from 259;
  `ruff check`/`ruff format --check` clean).
