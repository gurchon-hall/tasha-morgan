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
  `apply` atomically combined its cost (play-from-hand, §8 "used"
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
  (necessarily already-locked, Rulebook §4) `locked` state correctly
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

## OQ-41 - Self-oust by spending your last pool on a transfer (status: resolved)

- Situation: a Methuselah with exactly 1 pool could spend 1 transfer
  (or 4 transfers + 1 pool) and be ousted by their own influence-phase
  payment; the engine offered it.
- Rules/interactions: the rulebook's Influence Phase worked example
  "Nora" says she "cannot use both counters in her pool to put that
  vampire into play because that would put her out of the game";
  the user ruled: "auto-oust impossible à 2 et 3 joueurs, possible à
  4 et 5 joueurs" (earlier wording: "c'est un cas réservé aux parties
  à 3+p, bloquer dans le format 2p"; the later statement supersedes
  "3+p"). Blocked in the 2P format.
- Solution: `engine/phases/influence.py::_available_choices` offers
  `add_blood` and `bring_crypt` only when
  `engine/pool.py::can_afford_without_ousting(state, player, 1)` holds
  (pool >= 2). Hook-offered influence options (Wider View) spend no
  pool. Generalised to every voluntary self-paid pool cost by OQ-42.

## OQ-42 - Burning your whole pool for votes (status: resolved)

- Situation: `engine/politics.py::variable_pool_burn_vote_options`
  offered X = 1..pool, letting a Methuselah burn their entire pool for
  votes (Oxford University, England) and be ousted; the same held for
  every other self-paid pool cost (contest payments, Wider View's play
  cost, Kine Resources Contested's self share).
- Rules & interactions: no rulebook or card-ruling source. User ruling
  2026-10-13: "à 2 joueurs, tu peux tomber à 0 pools à cause de tes
  actions mais l'objectif étant de gagner, on va dire que cela est
  interdit quelle que soit la manière de perdre du pool" (with OQ-41's
  "auto-oust impossible à 2 et 3 joueurs, possible à 4 et 5 joueurs").
  A project simplification for the 2P duel (`docs/DECISIONS.md` D-9);
  pool lost to the opponent's actions still ousts normally.
- Solution: central helpers `engine/pool.py::can_afford_without_ousting`
  / `max_voluntary_spend` gate every voluntary option: influence
  transfers, burn-for-votes (X <= pool - 1, minus
  `pending["pool_reserve"]`), the four contest pay-or-yield decisions
  (only yield remains), Wider View's play, Kine Resources Contested
  (own share <= pool - 1, pool reserved during its referendum). Forced
  self-inflicted losses are not filtered; see OQ-43.

## OQ-43 - Forced self-inflicted pool loss may oust the payer (status: resolved)

- Situation: some effects make a Methuselah lose pool with no choice at
  the moment of loss (Fame's torpor burn of 3 and unlock-phase burn of
  1; Marcos Belegrad's burn for those who voted against; Kine Resources
  Contested if the caller's pool dropped).
- Rules & interactions: no rulebook or card-ruling source. User ruling
  2026-10-13: "fame continue de fonctionner normalement car aucun choix
  n'est fait une fois fame en jeu. les choix qui mène l'agent lui même
  à 0 sont interdits".
- Solution: a forced effect with no choice at resolution applies
  normally and may oust its controller (Fame unchanged). Any choice
  whose consequence, even downstream, takes the chooser to 0 is not
  offered: a vote against a Marcos Belegrad referendum is withheld when
  `pool - 1 - reserve < 1`, via `politics.VOTE_AGAINST_POOL_COST_HOOK`
  (checked at casting time, burn happens at tally). `docs/DECISIONS.md`
  D-9. Residual gap: OQ-45 (resolved).

## OQ-44 - Simultaneous ousts: who wins? (status: resolved)

- Situation: two Methuselahs can reach 0 pool in one resolution (Marcos
  Belegrad's tally burn, Kine Resources Contested, double Fame torpor in
  one strike pair); the engine silently picked the first processed.
- Rules & interactions: rulebook `5-ending-the-game.md`: "In the case of
  a tie there is no winner of the game"; EXCEPTION: a Methuselah ousted
  at the same time as their prey "gets the victory point but does not
  gain 6 pool counters". Card ruling on file (Kine Resources Contested,
  verified in `data/cards/101056.json`): "If multiple ousts happen,
  players whose prey gets ousted get a victory point, even if they are
  being ousted themselves. Only the surviving ones get 6 pool" [LSJ
  20000309] -- consistent with the EXCEPTION. User ruling 2026-10-13:
  "oust simultané semble ok si pas de solution de gagner" (reading B).
- Solution: both at 0 from the same event = tie, `game_over` with
  `winner = None` (`engine/pool.py::simultaneous_pool_losses` defers the
  oust check to the end of the event; `ousting.resolve_pending_ousts`).
  Each gets 1 VP and no pool per the EXCEPTION (each is the other's prey;
  no last-Methuselah VP). User ruling 2026-10-13 on the VP
  assignment: "1 VP chacun, conclusion = match nul"; the outcome is a
  draw. `docs/DECISIONS.md` D-10.

## OQ-45 - Kine allocation when every split zeroes the caller (status: resolved)

- Situation: Kine Resources Contested's caller chose the 4-point split
  after the vote; a Marcos Belegrad tally burn could leave no legal
  split (D-9), yet the allocation is mandatory.
- Rules & interactions: Rulebook §4 "The Referendum" lists step 1
  "Choose the terms" before step 2 "Polling"; the card text and rulings
  (LSJ 20000622, 20020819) are silent on timing. User ruling
  2026-10-13: "la répartition est verrouillée avant le vote puis fenetre
  d'avant votes (poison pill par exemple, pas au format 2p) puis le vote
  a lieu puis fenetre de fin de tally pour les réactions (delaying
  tactics par exemple) puis résolution des effets du vote puis fenetre
  d'action modifier de fin d'action (voter captivation par exemple)".
- Solution: the split is chosen and locked first
  (`cards/kine_resources_contested.py`), its self share must be
  affordable (pool >= share + 1) and is passed as `pool_reserve`, so
  the vote-time gates (Marcos against-cost, Oxford burn) always leave it
  payable. Windows after the tally (reactions beyond Marcos' mandatory
  burn; `REFERENDUM_RESOLVED` for Voter Captivation) have no engine
  dispatch yet. `docs/DECISIONS.md` D-9.

## OQ-46 - On the Qui Vive - no "woken" eligibility override (status: resolved)

- Situation: On the Qui Vive (krcg id 101321, Reaction): "Only usable by a
  locked minion... This minion wakes (they ignore the requirement to be
  unlocked for playing reaction cards and attempting to block until the end
  of the action). If this minion is an ally, they do not unlock as normal
  during their next unlock phase." Unlike Organized Resistance/Second
  Tradition: Domain's "burn to unlock and force a block" shape
  (`BLOCK_CANDIDATE_INJECTION_HOOK`, OQ-26), this card forces nothing and
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
- Rules/interactions: plain card text; no ruling settles the engine shape
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

## OQ-47 - Weighted Walking Stick - no "Before Range" play window (status: resolved)

- Situation: Weighted Walking Stick (krcg id 102169, Combat): "Only usable
  before range is determined during the first round. Put this card with 5
  counters on it on this minion; it becomes a melee weapon equipment that
  can strike: strength+1 damage. For each damage inflicted by this strike
  (even if prevented), burn 1 counter from this card." Combat Sequence step
  1 ("Before Range: Play cards before range is chosen") had no call site,
  hook, or round/combat-scoped state at all in `engine/combat.py::
  run_combat` — distinct from, and strictly before, step 2 "Determine
  Range" (maneuvers, already built, OQ-25/27/28).
- Rules/interactions: plain card text and the Combat Sequence step
  ordering; no ruling bears on the engine shape. `engine/cards.py::
  CardAttachment` already carries `counters`, and `COMBAT_STRIKE_OPTION_
  HOOK`'s existing provider contract (pre-prevention, post-reduction
  damage) already supplies what "for each damage inflicted ... even if
  prevented" needs — neither needed a change.
- Solution: added `Hook.BEFORE_RANGE`/`engine/combat.py::BEFORE_RANGE_HOOK`,
  dispatched via `_ask_before_range` (the same two-sided `hooks.
  resolve_impulse_window` shape as `END_OF_ROUND_HOOK`, acting combatant's
  controller first, OQ-3) exactly once per combat, gated by a local
  `before_range_offered` flag so it never re-fires on a later round of the
  same combat. A provider's own `apply(state)` attaches a card directly
  (`engine/attachments.py::attach_card`, mirroring `cards/celerity.py`'s
  non-unique-attachment pattern); the strike/counter-burning half needs no
  further engine change, confirmed above. Weighted Walking Stick's own card
  module is now implemented against this mechanism (`cards/
  weighted_walking_stick.py`, `Status.IMPLEMENTED`).

## OQ-48: On the Qui Vive - no wake-before-candidates hook (status: resolved)

- Situation: OQ-46's own `VampireInPlay.woken`/`clear_woken_vampires`/
  `AllyInPlay.skip_next_unlock` primitives let `is_ready_unlocked` honor a
  woken locked vampire everywhere it is already consulted (the block
  candidate list, every existing reaction-card provider's own eligibility
  check), but nothing in the engine ever offered a *defender*-side option to
  set `woken = True` on one of their own locked vampires *before*
  `engine/action.py::attempt_block`'s own candidate list
  (`state.ready_unlocked_vampires(defender)`) is computed each time around
  its retry loop -- the moment that matters for this card's primary
  "attempting to block" clause. The acting side had exactly this shape
  already (`INTERCEPT_DECREASE_HOOK`/`STEALTH_INCREASE_HOOK`, offered to
  `actor` via `hooks.offer_until_pass` at the very top of that same loop,
  before any candidate exists or is recomputed, OQ-30/OQ-39) -- no symmetric
  offer to `defender` existed anywhere in that function, or in any other
  hook dispatched before a block candidate is fixed.
- Rules/interactions: a missing engine primitive, not a ruling question
  (same category as OQ-46's own "engine-internal design choices, not ruling
  questions"); `BLOCK_CANDIDATE_INJECTION_HOOK` (OQ-26) was considered and
  rejected as the vehicle instead, since `attempt_block` always treats a
  chosen option from it as an *unconditional* successful block ("never runs
  the stealth/intercept ping-pong for this candidate"), contradicting this
  card's own block attempt (fully subject to normal stealth/intercept
  resolution, per [TOM 19951129] "the minion need not attempt to block...
  that is merely an option").
- Solution: added `WAKE_LOCKED_MINION_HOOK` (`cards/registry.py::
  Hook.WAKE_LOCKED_MINION`), offered to `defender` via `hooks.offer_until_
  pass` at the top of `attempt_block`'s retry loop, immediately after the
  two acting-side hooks' own offers there (actor's own proactive
  opportunities keep going first, Rulebook §2 Sequencing / CLAUDE.md rule
  4's "acting Methuselah gets the impulse first") and strictly before
  `candidates = state.ready_unlocked_vampires(defender)` is (re)computed,
  so a chosen option's own `apply` setting `woken = True` is picked up by
  that very computation, every time around the loop including on a retry
  (OQ-11). Same "no return value needed, `apply` just mutates state"
  contract as its two siblings. A provider waking an *ally* instead sets
  `AllyInPlay.skip_next_unlock = True` (OQ-46's own field, reused, not
  duplicated) -- allies are never themselves offered as block candidates in
  this engine (out of scope, OQ-46's own solution note), so that branch of
  the contract matters for a future ally-side use of this same hook, not for
  `attempt_block` itself. On the Qui Vive's own card module is not written;
  the primitive is complete.

## OQ-50: Combat Sequence - Steal Blood strike effect unbuilt (status: open)

- Situation: `rules-auditor`, auditing `engine/combat.py` generally (not
  against a specific card), found the **Steal Blood** strike effect
  (occurs before the mend damage step, even if damage is inflicted
  simultaneously) entirely unbuilt. Unlike its two siblings found in the
  same audit (Combat Ends, First Strike -- deferred, `docs/DECISIONS.md`
  D-12), Steal Blood is live in the active 2026-10-03 2P allowed list:
  Diversion (100563), Theft of Vitae (101966), Form of the Cobra
  (102224) and Hunger of Marduk (102227) are all unimplemented `Combat`
  cards printing "Strike, ranged: steal N blood or life (becoming
  blood)" -- an alternate strike resolution (blood theft instead of
  damage) that `engine/combat.py::StrikeDamage`/`_resolve_strike_pair`
  has no path for.
- Sources read: Rulebook §4 Detailed Turn Sequence (live-fetched
  2026-10-15, also cached `data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md:1006-1053`): Steal Blood's "before the
  mend damage step... even if damage is inflicted simultaneously"; krcg
  card text for the four cards above, cross-checked against
  `data/formats/2p/2026-10-03.json`.
- Candidate readings: N/A -- a missing engine primitive, not a ruling
  ambiguity.
- Impacted code/cards: `src/vtesbot/engine/combat.py`
  (`StrikeDamage`/`run_combat`/`_resolve_strike_pair`). Blocks Diversion,
  Theft of Vitae, Form of the Cobra, Hunger of Marduk (none written yet).

## OQ-51: Politics - Contested Titles mechanism unimplemented (status: open)

- Situation: `rules-auditor`, auditing `engine/politics.py` generally,
  found that two *different-named* vampires both claiming the same
  scoped title (Prince/Baron per city, Justicar/Inner Circle per clan,
  Archbishop per city, Regent unique -- the last two confirmed live by
  a later `rules-auditor` pass once `TITLE_VOTES` was fixed to grant
  Sabbat-title votes, same gap) have no contest mechanism at all:
  `TITLE_VOTES`/`_collect_vote_sources`
  grants full votes unconditionally, with no competing-title-holder
  check, no 1-blood-per-unlock cost, no "treated as no title" suppression
  while contested. `CryptCard` also has no city/clan scope field to even
  detect this. Distinct from the already-implemented 2P same-named
  vampire exception (two copies of the same vampire -> title not
  contested, correctly built).
- Sources read: Rulebook §4 Advanced Rules "Contested Titles" (live-
  fetched 2026-10-15, cached `data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md:65-84`) and §6 Vampire Sects
  (`6-vampire-sects.md:30-61`) for the per-city/per-clan scoping; 2P
  variant page re-checked live 2026-10-15
  (`https://www.vekn.net/two-player-format/655-two-player-variant-for-
  vampire-the-eternal-struggle`) specifically for a 2P-specific title
  delta beyond the already-built same-named exception -- it states
  only "If two contested vampires (two copies of the same vampire)
  have a title, their title is not contested" and no other
  title-related rule. The general rulebook contested-titles mechanism
  (different-named vampires sharing a scoped title) is therefore
  unmodified in 2P and is exactly what this entry's gap is about.
- Candidate readings: N/A -- the rule itself is clear; only the
  data-modeling approach (how to add city/clan scope to `CryptCard`) is
  undecided. Confirmed latent against the active 2026-10-03 list (no two
  legal crypt cards currently share a contestable title+scope), so a
  future VEKN list update could make this live with zero code changes.
- Impacted code/cards: `src/vtesbot/engine/politics.py` (`TITLE_VOTES`,
  `_collect_vote_sources`), `src/vtesbot/engine/cards.py` (`CryptCard`).
  No card blocked yet.

## OQ-52: Observation - `wounded` not gated by hidden-identity (status: open)

- Situation: `rules-auditor`, auditing `engine/observation.py` against
  CLAUDE.md §5's information-hiding invariant, found `build_observation`'s
  `vampire_view` gates only `blood`/`name`/`capacity` behind
  `visible_identity` (`zone != "uncontrolled" or controller == viewer`);
  `wounded` is read straight off `VampireInPlay` with no such gate.
  Currently inert: every `zone = "uncontrolled"` call site
  (`engine/setup.py`, `engine/phases/influence.py`, `cards/
  wider_view.py`) only ever sets it on a freshly-constructed
  `VampireInPlay` (`wounded=False` by dataclass default); no code path
  moves an already-revealed, possibly-wounded vampire back to
  `"uncontrolled"`.
- Sources read: CLAUDE.md §5 ("agents receive an `Observation`... never
  the raw `GameState`. A bot must not read... face-down uncontrolled
  vampires.") -- a project invariant, not an external VEKN source.
- Candidate readings: N/A -- missing explicit gate, not a ruling
  question. A future card effect returning a vampire face-down to the
  crypt while it carries `wounded`/`locked` state would leak that state
  through this exact path, with no test positioned to catch it.
- Impacted code/cards: `src/vtesbot/engine/observation.py`
  (`build_observation`/`vampire_view`). No card blocked yet.

## OQ-49 - Fiorenza Savona - no vote-cast bonus hook (status: resolved)

- Situation: Fiorenza Savona (krcg id 201616): "Camarilla: If you burn the
  Edge for a vote, you get +1 vote. If you burn a political action card for
  a vote, you get +1 vote." OQ-6's general referendum mechanism gives
  `_collect_vote_sources` a fixed set of `VoteSource`s with `votes` baked in
  before casting, and neither `POLLING_STEP_HOOK` phase nor
  `REFERENDUM_TALLIED_HOOK` can add a bonus to one *specific other* source's
  own vote count at the moment it is actually cast -- a missing engine
  primitive, not a ruling ambiguity.
- Rules/interactions: plain printed text; no ruling on file. User ruling
  2026-10-14 settled the one open scope question: "burning a political
  action card for a vote" is specifically the non-caller's
  `political_action_card_hand:{other_player}` burn-from-hand source (the
  only one actually burned for a vote), never the caller's own
  `political_action_card:{caller_player}` source (played/shown, not
  burned).
- Solution: added `VOTE_SOURCE_CAST_BONUS_HOOK` (`cards/registry.py::
  Hook.VOTE_SOURCE_CAST_BONUS`), dispatched by `engine/politics.py::
  _cast_votes` the instant a source is cast -- after its own cast-time side
  effects, before its votes are added to the tally *and* logged into
  `casts` (so an OQ-37 mid-cast cancellation of that same source
  retroactively subtracts the bonus back out too, no special case). Context:
  `caster`, `burns_edge`, `burns_pac_from_hand`, `direction`. Fiorenza
  Savona's own card module (`cards/fiorenza_savona.py`, `Status.
  IMPLEMENTED`) gates on either flag plus "caster controls an in-play
  (not uncontrolled/burned/removed) Fiorenza" -- no "while ready" qualifier
  is printed, so no zone/locked gate beyond that.

## OQ-53: Politics - Prisci Block has no engine mechanism   (status: open)

- Situation: `rules-auditor` found `TITLE_VOTES` wrongly claimed Sabbat
  titles were "out of pool scope" (now fixed: Bishop/Archbishop/Cardinal/
  Regent added as flat per-ready-vampire vote values). Priscus does not
  fit that same flat table: §6 Vampire Sects describes "the prisci as a
  group have 3 votes," cast via its own 1-ballot-per-ready-priscus
  sub-referendum (for/against/abstain on a tie), shifting as ballots are
  cast during the main referendum's own polling step -- a group/
  block-voting mechanism, not a per-vampire `VoteSource`.
- Sources read (with URL/section): Rulebook §6 Vampire Sects, live
  re-fetch succeeded 2026-10-15 (`https://www.vekn.net/rulebook`),
  matching the local cache verbatim
  (`data/sources/rulebook/2026-10-09/6-vampire-sects.md:70-80`, fetched
  2026-10-09, `dateModified` 2025-11-16): "The prisci as a group have
  3 votes. During a referendum, the prisci block of 3 votes is cast
  'for' or 'against' the referendum according to the prisci
  sub-referendum. Each ready priscus provides 1 ballot for this
  sub-referendum, and votes may not be used in this sub-referendum.
  [...] Whichever side has the greater number of ballots in the
  sub-referendum gains 3 votes in the main referendum. If the
  sub-referendum is tied, the prisci block abstains [...] the prisci
  block of 3 votes might shift [...] as the majority in the
  sub-referendum changes."
- Candidate readings: confirmed Reading A -- the quoted text above is
  itself a description of exactly a nested sub-referendum (its own
  ballot-cast/tally loop, feeding a single for/against/abstain
  `VoteSource` into the main referendum's own tally, re-evaluated as
  ballots are cast); no "B" alternative is needed. Still unbuilt: this
  confirms the engine shape to build, it does not build it.
- Impacted code/cards: `src/vtesbot/engine/politics.py` (`TITLE_VOTES`,
  `_collect_vote_sources`, `_cast_votes`). No card blocked yet (the active
  2026-10-03 list has exactly one Priscus, krcg id 201760 Khin Aye; her own
  printed text is independent of this mechanism).

## OQ-54: Politics - Blood Hunt referendum polling order (status: open)

- Situation: `rules-auditor`, reviewing the new diablerie-resolution
  subsystem (`engine/diablerie.py::resolve_diablerie`), flagged that
  the mandatory, automatic Blood Hunt referendum (Rulebook §4
  "Diablerie" > "The Blood Hunt") has no card cast to establish a
  natural "caller" with impulse first (Rulebook §2 Sequencing). Every
  other referendum this engine resolves is reached only via an
  actually-cast political action card. `resolve_diablerie` picks the
  diablerist's own controller as `resolve_referendum`'s `caller_player`
  (so she polls first), reasoning that impulse "returns to the acting
  Methuselah" of the triggering minion action (the diablerie attempt
  itself). Does not affect vote-source correctness (OQ-6's resolved
  mechanism, and this call's own `include_caller_card_vote=False` fix,
  are both symmetric regardless of who is nominally "caller") -- only
  who polls first.
- Sources read: Rulebook §4 "Diablerie"/"The Blood Hunt" (live-fetched
  2026-10-15, matching cached `data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md:1076-1118` verbatim): "a referendum is
  automatically and immediately conducted... Otherwise, this
  referendum is handled just like any other" -- settles that normal
  polling/tally happens, but states no explicit polling-order rule for
  a referendum with no calling card. Rulebook §2 Sequencing (impulse
  returns to the acting Methuselah) checked but not card/mechanism-
  specific enough to close this without inference.
- Candidate readings: (A) diablerist's controller polls first, as
  currently implemented (impulse-returns-to-acting-Methuselah
  reading). (B) some other fixed order (e.g. victim's controller
  first, as the one "responding" to being diablerized). No source
  found contradicting (A) or mandating (B); flagged as non-blocking by
  `rules-auditor` since no implemented card's text currently depends
  on Blood Hunt polling order.
- Impacted code/cards: `src/vtesbot/engine/diablerie.py`
  (`resolve_diablerie`'s call into `engine/politics.py::
  resolve_referendum`). No card currently depends on this order;
  revisit before implementing a future card whose text is sensitive to
  who polls first in this specific referendum.
