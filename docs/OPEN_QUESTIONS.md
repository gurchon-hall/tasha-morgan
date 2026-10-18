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

## OQ-55: Soak - no round_state in damage-prevention hook (status: resolved)

- Situation: Soak (krcg id 101817, Combat): "A vampire can play only
  one Soak each round." Its basic/superior clauses ("[for] Prevent 2
  non-aggravated damage." / "[FOR] Prevent 4 non-aggravated damage.")
  are each fully implementable against the already-wired
  `DAMAGE_PREVENTION_HOOK` (`engine/damage.py::apply_damage`'s
  "Prevent step") -- gating on `damage_box["normal"] > 0`, capping
  prevention at whatever is left [RTR 20041202], never touching
  `damage_box["aggravated"]` [LSJ 20040812-2] [PIB 20130327], no
  option offered once there is nothing left to prevent [LSJ 20001114].
  Only the printed "once per round" limit has no mechanism:
  `apply_damage` receives `round_state` as a parameter (the same
  round-scoped scratch dict `engine/combat.py::run_combat` creates
  fresh each round for every other per-round cap, e.g.
  `ADDITIONAL_STRIKE_LIMIT_KEY`) but never threads it into the
  `context` dict it builds for `hooks.offer_until_pass(state,
  DAMAGE_PREVENTION_HOOK, player, context={"vampire": ...,
  "damage": damage_box})` -- no card-side provider can see or write a
  round-scoped flag at this hook. The restriction is reachable within
  one round: `_resolve_strike_pair` is called again for each
  additional-strike pair with the *same* `round_state`, so the same
  vampire can take damage, hence be offered `DAMAGE_PREVENTION_HOOK`,
  more than once in one round (e.g. an additional-strike grant landing
  a second hit).
- Sources read: krcg (`data/cards/101817.json`, installed krcg 4.18
  `krcg.vtes.VTES`), card text and all 4 on-file rulings quoted above;
  `src/vtesbot/engine/damage.py::apply_damage`,
  `src/vtesbot/engine/combat.py` (`ROUND_STATE_CONTEXT_KEY`,
  `_resolve_strike_pair`, `_ask_additional_strike`,
  `additional_strike_limit_used`/`mark_additional_strike_limit_used` as
  the existing round-scoped-cap convention).
- Candidate readings: N/A -- a missing engine primitive, not a ruling
  ambiguity. Only the data-plumbing approach (how `round_state` reaches
  `DAMAGE_PREVENTION_HOOK`'s context) is undecided.
- Impacted code/cards: `src/vtesbot/engine/damage.py::apply_damage`
  needed `round_state` threaded into the `DAMAGE_PREVENTION_HOOK`
  context, mirroring `ROUND_STATE_CONTEXT_KEY`'s existing convention.
  Blocked Soak (101817). Also blocked Rolling with the Punches's own
  (101649, `src/vtesbot/cards/rolling_with_the_punches.py`) superior
  "[FOR] Burn 1 blood to prevent all damage from the opposing minion's
  strikes this round." clause -- its basic "[for] Prevent 1 damage."
  clause had no gap and was already implemented. `round_state` being
  round-(hence combat-)scoped already identifies "the opposing minion"
  implicitly (one `run_combat` call is always exactly one 1-on-1
  combat, so no separate opponent identifier is actually needed once
  `round_state` reaches the hook), but a second, distinct gap remained
  even after that fix landed: this clause, once chosen, makes
  prevention automatic and mandatory for every further strike that
  round -- not a fresh optional choice re-offered each time.
  `DAMAGE_PREVENTION_HOOK`'s own dispatch (`hooks.offer_until_pass`)
  had no primitive for "this option, once taken, applies
  unconditionally from now on this round" -- only "offered now, freely
  declinable" (a provider mutating `damage_box` directly from inside
  its own `offer`-time code, bypassing `apply` entirely, would have
  dodged that contract rather than use it, and was rejected as exactly
  the kind of card-module workaround CLAUDE.md §2 rules out). Both
  gaps are now closed; see Solution.
- Solution: `rules-engineer` threaded `ROUND_STATE_CONTEXT_KEY:
  round_state` into `apply_damage`'s `DAMAGE_PREVENTION_HOOK` context
  dict (`engine/damage.py`, which now also owns the canonical
  `ROUND_STATE_CONTEXT_KEY` definition itself -- `engine/combat.py`
  re-exports the same object, to avoid a circular import), exactly
  mirroring `ADDITIONAL_STRIKE_LIMIT_KEY`'s existing read/write
  convention; a provider missing `round_state` degrades to "cap
  unused," same as every other round-scoped cap in this codebase.
  Soak (101817) is now implemented against it (`cards/soak.py`,
  `Status.IMPLEMENTED`), including a test reproducing the
  two-separate-hits-in-one-round case that motivated this entry. For
  the second gap, `rules-engineer` added `MANDATORY_FULL_PREVENTION_KEY`
  / `mandatory_full_prevention_active` /
  `mark_mandatory_full_prevention_active` (`engine/damage.py`): a
  per-vampire-id, round-scoped flag that `apply_damage` itself checks
  and, once set, unconditionally zeroes all further damage against
  that vampire for the rest of the round before
  `DAMAGE_PREVENTION_HOOK` is even dispatched -- distinct from the hook
  itself, which still only ever offers a freely-declinable choice.
  Rolling with the Punches (101649) is now fully implemented against
  both primitives (`cards/rolling_with_the_punches.py`,
  `Status.IMPLEMENTED`): its superior clause's `apply` burns 1 blood,
  zeroes the triggering strike's own `damage_box`, and marks the flag
  so every later strike this round is automatically covered.

## OQ-56: Propaganda - who chooses which vampire to lock (status: resolved)

- Situation: Propaganda's (krcg 101495) superior clause reads "...the
  target Methuselah locks a ready unlocked minion they control." No
  on-file ruling (for Propaganda, or for the structurally similar
  Brujah Debate/Sowing Dissension) settles whether the affected
  (target) Methuselah or the acting Methuselah chooses which qualifying
  vampire is locked, when there is no tie to break.
- Rules/interactions: live krcg text confirms the grammatical pattern
  ("[that Methuselah] locks a [vampire] they control") but Brujah
  Debate's own on-file ruling ([LSJ 19980224]) only resolves a
  tie-break among several vampires all "the oldest Brujah" -- not a
  general "sentence subject chooses" default. No general VEKN default
  for an unnamed decision-maker was found live.
- Solution (user ruling): Reading A -- the target (affected) Methuselah
  chooses, matching `engine/action.py::force_lock_ready_unlocked_
  minion`'s existing default. No code change needed.
  `cards/propaganda.py`'s superior clause may be wired to it as-is.

## OQ-57: Action cards - no cancel-as-played path (status: resolved)

- Situation: `rules-auditor`, reviewing Propaganda/Dominate Kine,
  found `engine/phases/minion.py::_perform_action_card` called
  `option.apply(state)` directly, never through `engine/hooks.py::
  apply_chosen_option` -- so no Reflex-type card could ever cancel an
  Action card "as played." A first fix pass introduced two further
  problems a follow-up audit caught: (1) the replacement-card draw ran
  *before* the cancel window instead of after; (2) no generic "same
  named action card at most once per turn" cap existed anywhere,
  already live-violated by every implemented Action card (Dominate
  Kine, Propaganda, Fleetness, Enchant Kindred, Disputed Territory,
  Kine Resources Contested, Line Brawl, Parity Shift).
- Rules/interactions: Rulebook §2 Card Types, "Library Cards" Advanced
  Rules (`data/sources/rulebook/2026-10-09/2-card-types.md:124-126`):
  "Some effects can cancel a card 'as it is played.' ... Even drawing
  to replace cards, comes after this time period." §3 "Cancel a card"
  (`3-playing-the-game.md:103-108`): a cancelled card is still
  considered played; an action card's own minion does not lock and
  "they can play the same action card again." §4 Detailed Turn
  Sequence (`4-detailed-turn-sequence.md:188-191`): "A minion cannot
  play (unless cancelled) the same named action card more than once
  each turn, even if they unlock" -- scoped per-minion, not
  per-controller.
- Solution: `engine/hand.py::remove_from_hand`/`draw_replacement_card`
  split the physical-card-removal and replacement-draw steps;
  `_perform_action_card` now sequences `option.apply` -> cancel offer
  (`hooks.offer_cancel_as_played`) -> unconditional replacement draw
  -> (only if not canceled) mark the per-turn cap and run
  `perform_minion_action`. `VampireInPlay.action_card_played_turn`
  (name-keyed, per-minion, storing the turn last played) backs
  `action_card_already_played_this_turn`/
  `mark_action_card_played_this_turn`, checked by all 8 real
  `ACTION_CARD_PLAY_HOOK` providers. Loup (Action Modifier, not
  Action) and `lucinde_alastor.py` (never plays a card from hand) are
  both correctly out of scope, confirmed rather than assumed.

## OQ-58: Observation - no attachment visibility (status: resolved)

- Situation: `rules-auditor`, reviewing Pulled Fangs, found
  `engine/observation.py::VampireView` has no `attachments` field at
  all, while a played attachment card (Pulled Fangs, Perfectionist,
  Weighted Walking Stick) is also left sitting in `Observation.
  ash_heap` (`play_from_hand` appends there unconditionally; nothing
  removes it once the same physical card becomes a live
  `CardAttachment`).
- Rules/interactions: CLAUDE.md §5 (information-hiding invariant);
  Rulebook §3 "Playing a Card" ("showing the card") confirms an
  attachment is always public once played -- not a ruling question,
  a project observation-fidelity gap.
- Solution: added `engine/observation.py::AttachmentView`
  (`instance_id`/`krcg_id`/`name`/`controller`/`counters`/
  `is_equipment`, `zone == "attached"` only) and
  `VampireView.attachments`, gated behind the existing
  `visible_identity` check (defensive -- no attach path in this
  engine ever targets a face-down uncontrolled vampire today).
  `ash_heap` double-listing fixed by a count-based filter
  (`_live_attachment_counts_by_controller`/`_visible_ash_heap`): hides
  at most as many same-`krcg_id` `ash_heap` entries as there are
  currently-live attachments of that id. `rules-auditor` noted this is
  index-based, not identity-based (could in principle hide a different
  same-named copy's entry than the one that actually became the
  attachment), but confirmed harmless under `ash_heap`'s own
  name-only, display-only shape -- worth revisiting only if `ash_heap`
  ever gains instance-level fidelity.

## OQ-59: Allies - no bleed/combat action path (status: open)

- Situation: OQ-46/OQ-48 already recorded "ally bleed/block/combat
  participation stays out of engine scope" as a deliberate design
  choice, and built only the unlock-side primitives for a future
  ally-acting path (`engine/phases/unlock.py::_unlock_own_allies`,
  `AllyInPlay.skip_next_unlock`) -- neither `engine/action.py` nor
  `engine/combat.py` has any path for an ally to initiate a bleed, be
  blocked, block, or strike. Checked against the active 2026-10-03 2P
  allowed list's 9 Ally cards: 6 of 9 need this capability to be
  implemented correctly -- Bone Shambler (102293, bleed 1), Political
  Ally (101411, bleed 3), Double Deuce (102220, bleed 1, strength 1),
  Heartrender (102327, bleed 1, strength 1 -- its own Ⓓ ability also
  needs it to be a legal actor), City Star Taxi (102234, explicit
  "can strike"/maneuver/combat text despite 0/0 stats), The Vozhd of
  Juiz de Fora (102364, strength 4, "can enter combat with a vampire
  as a Ⓓ action"), The Vozhd of Sofia (102267, strength 3, strike +
  "can enter combat with a minion as a Ⓓ action"). Only 47th Street
  Royals (102217, implemented, passive-only) and Vagabond Mystic
  (102087, unimplemented, passive lock-only ability) avoid the gap.
- Sources read: Rulebook §4 Detailed Turn Sequence (live-fetched
  2026-10-16, matches cached `data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md:163-166`), verbatim: "a ready vampire
  may generally perform one of two basic actions ... bleed or hunt,
  whereas a ready ally may perform only one basic action ... bleed";
  same section's Combat text has no ally-specific carve-out ("only
  ready minions can participate in combat"), and `:1021-1029`'s
  worked example has an ally striking in combat normally. krcg card
  text for all 9 Ally entries in `data/formats/2p/2026-10-03.json`,
  cross-checked.
- Candidate readings: N/A -- not a ruling ambiguity, a missing/
  deferred engine capability (same category as OQ-46/48's own
  classification).
- Impacted code/cards: `engine/action.py` (no ally action-initiation
  path), `engine/combat.py` (no ally-as-combatant path); the
  OQ-46/48 unlock-side primitives are built but unused by either.
  Blocks Bone Shambler, Political Ally, Double Deuce, Heartrender,
  City Star Taxi, The Vozhd of Juiz de Fora, The Vozhd of Sofia
  (none written yet).

## OQ-60 - Precognition - no round-1-only combat grant from block (status: resolved)

- Situation: Precognition (krcg id 101475, Reaction, Mono Auspex):
  "[aus] +1 intercept. [AUS] As above, and this vampire can prevent 1
  damage during the first round of the resulting combat if they
  block." The superior clause's damage-prevention half needed two
  things no hook surface exposed: (1) a way for that reaction's own
  `apply()` (run during the block attempt's stealth/intercept
  resolution, before `run_combat` is even called) to hand a grant
  forward into the *later, separate* `run_combat` call for that same
  blocker; and (2) a way for a `DAMAGE_PREVENTION_HOOK` provider to
  tell "is this round 1 of the current combat."
- Rules/interactions: "The damage prevention can only be used if the
  block is successful, and only in the resulting (block-induced)
  combat." [LSJ 20010813]; "does not carry over to a follow-up combat"
  [LSJ 20010819-2]; "is provided again if a second block happens on
  the same action" [LSJ 20010814-2] — together read as a one-shot
  grant, tied to the specific vampire that played the card and that
  same vampire ending up as the blocker, usable at most once, only in
  round 1 of the one resulting combat.
- Solution: `engine/action.py::grant_block_time_combat_effect` records
  a grant into the block attempt's own `pending[PENDING_BLOCK_TIME_
  COMBAT_GRANT_KEY]`, keyed by the reacting vampire's instance id;
  `perform_minion_action` forwards only the entry keyed by the
  eventual successful `blocker` into that one `run_combat` call's
  `initial_combat_state` (`engine/combat.py::seed_block_time_combat_
  grants`/`block_time_combat_grant_available`/`consume_block_time_
  combat_grant`, keyed `BLOCK_TIME_COMBAT_GRANT_KEY`) — a grant for
  any other candidate is simply never read, and nothing carries into a
  second `run_combat` call. `engine/damage.py::is_round_one` reads a
  new `ROUND_NUMBER_KEY` that `run_combat` now writes into `round_
  state` at the top of each round, and `apply_damage` now also threads
  `combat_state` into `DAMAGE_PREVENTION_HOOK`'s own context alongside
  `round_state`. Generic mechanism proven in `tests/rules/test_block_
  time_combat_grant.py`; Precognition itself is now `Status.IMPLEMENTED`
  (`src/vtesbot/cards/precognition.py`, tests in `tests/cards/
  test_precognition.py`).

## OQ-63 - Corruption counters wrongly attachment-bound (status: resolved)

- Situation: `cards/aniel.py`'s own corruption-counter clause (shipped
  under OQ-62) modeled "burn 1 corruption counter... from another ready
  minion" as requiring a `CardAttachment` present on the target vampire
  with a positive `counters` field -- i.e. a corruption counter could only
  exist riding on an attachment. Caught in review before any other card
  built on the same (wrong) assumption.
- Rules/interactions: verified via live `krcg.load()` text for every
  legal-2P card using the "corruption counter" keyword: Aniel (201666,
  quoted above); Sergio Bueno (201662, Anarch Baron of Santo Domingo,
  unimplemented): "Minions with 1 or more of your corruption counters must
  burn 1 blood or life to attempt to block Sergio." [LSJ 20011022: passive
  ability applies even in torpor]; The Platinum Protocol (102232, library
  Action, unimplemented): "...[pro] Put 1 corruption counter on a minion
  controlled by the target Methuselah if the bleed is successful (for 1 or
  more)." [ANK 20240706]/[LSJ 20080608]: counter target chosen at
  resolution, not declaration; [ANK 20200925]/[ANK 20211105]: placing a
  counter does not allow stealing it. Revelation of Ecstasy (101624, not
  on the active 2P list, cited only as the stale precedent that misled the
  original implementation): "...put 1 corruption counter on the target
  minion. If the number of your corruption counters on the minion equals
  or exceeds their capacity or cost, you can burn those counters to steal
  the target minion." Every one of these texts puts the counter on the
  minion itself, never on an attached card; no legal-2P card ever puts a
  corruption counter on an attachment.
- Solution: added `VampireInPlay.corruption_counters` (`engine/state.py`),
  a `dict[str, int]` keyed by the placing Methuselah's `player_id` --
  Sergio Bueno's own "YOUR corruption counters" wording is placer-scoped,
  not a flat total, even though a 2P duel (CLAUDE.md §3) only ever has one
  possible placer besides the vampire's own controller; chosen over a flat
  `int` as the more future-proof shape per the task's own direction, same
  design-call precedent as OQ-61/62. `engine/corruption.py::
  add_corruption_counters`/`burn_corruption_counters` (floored at zero,
  mirroring `engine/damage.py::add_blood`/`engine/allies.py::add_life`'s
  own capped-helper shape, here capped below instead of above) /
  `total_corruption_counters`. `cards/aniel.py`'s corruption-counter clause
  now offers one option per placer with a counter present on the targeted
  vampire, burning via `burn_corruption_counters` directly -- no attachment
  involved. `engine/phases/minion.py::build_attachment_removal_action_
  spec`'s own docstring (which had cited Revelation of Ecstasy's corruption
  counters as a precedent for reusing `CardAttachment.counters`) corrected
  to cite Weighted Walking Stick's own ammo count instead, and to note the
  new field's existence. `tests/rules/test_corruption_counters.py` proves
  the primitive generically; `tests/cards/test_aniel.py` updated to match.
  `add_corruption_counters` itself is not yet exercised by any card (no
  implemented card places a corruption counter) -- left in place for
  Sergio Bueno/The Platinum Protocol, neither built here.

## OQ-64 - Sergio Bueno - no block-attempt mandatory cost-gate hook (status: resolved)

- Situation: Sergio Bueno (krcg 201662): "Minions with 1 or more of your
  corruption counters must burn 1 blood or life to attempt to block
  Sergio." Neither `block_candidate_predicate` (a stateless, per-action-
  card property filter) nor `BLOCK_CANDIDATE_EXCLUSION_HOOK` (an
  actor-chosen exclusion) fit: this is a passive crypt ability spanning
  every action type its vampire ever performs, and a mandatory cost paid
  the instant a candidate attempts, win or lose -- not merely a boolean
  filter.
- Rules/interactions: a missing engine primitive, not a ruling ambiguity
  (same category as OQ-46/48/59's own "missing/deferred engine capability"
  classification) -- the card text and its one on-file ruling
  ([LSJ 20011022], moot here since the engine never offers a torpid
  vampire as `acting_vampire` in the first place) already settle the rule.
- Solution: `engine/action.py::BlockAttemptCost`/`BLOCK_ATTEMPT_COST_HOOK`,
  dispatched per-candidate (both the hardcoded `ready_unlocked_vampires`
  list and `BLOCK_CANDIDATE_INJECTION_HOOK` options) via the new
  `engine/hooks.py::collect` combinator; a candidate that cannot afford an
  applicable cost is not offered at all, one that can pays it
  (`_pay_block_attempt_costs`) the instant it is chosen, before the
  stealth/intercept duel. Generic mechanism proven in `tests/rules/
  test_block_attempt_cost.py`; Sergio Bueno (201662) is now
  `Status.IMPLEMENTED` (`src/vtesbot/cards/sergio_bueno.py`, tests in
  `tests/cards/test_sergio_bueno.py`).

## OQ-65 - Forced Confessional - no force-block-attempt-failure hook (status: resolved)

- Situation: Forced Confessional (krcg 102250): "[DOM] That attempt fails
  and the blocking minion cannot attempt to block this action again." The
  "cannot attempt to block this action again" half fits the existing
  `BLOCK_CANDIDATE_EXCLUSION_HOOK`/`PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY`
  primitive directly (a provider may write to it from any hook's own
  `apply`, not only from that hook's own proactive offer point). "That
  attempt fails" does not: every existing acting-side tool at the reactive
  point a block attempt is already in progress
  (`INTERCEPT_DECREASE_HOOK`/`STEALTH_INCREASE_HOOK`, OQ-30/31/39) only ever
  adjusts the `stealth`/`intercept` numbers `_duel_stealth_intercept`
  compares, then loops back to let the defender respond again -- none
  terminates that comparison outright. An extreme decrease (e.g. -999)
  would still leave the defender free to add intercept back before the
  duel ends, which is not what "that attempt fails" (an unconditional,
  immediate result) means.
- Rules/interactions: a missing engine primitive, not a ruling ambiguity
  (same category as OQ-46/48/59/64's own classification) -- the card text
  has no on-file ruling (`rulings == []`) and needs none to settle the
  engine shape.
- Solution: added `FORCE_BLOCK_ATTEMPT_FAILURE_HOOK` (`cards/registry.py::
  Hook.FORCE_BLOCK_ATTEMPT_FAILURE`), offered alongside `INTERCEPT_DECREASE_
  HOOK`/`STEALTH_INCREASE_HOOK` in `_duel_stealth_intercept`'s own "block
  currently succeeds" branch, merged into the same `Decision` via
  `_ask_stealth_or_modifier`. Choosing it makes `_duel_stealth_intercept`
  return a new third value, `forced_failure=True`, read by `attempt_block`
  before it ever compares `intercept >= stealth` -- the attempt is treated
  as failed outright (loops back, same as any other failed attempt),
  independent of the numbers in play. Proven generically in `tests/rules/
  test_force_block_attempt_failure.py`. Forced Confessional (102250) is now
  `Status.IMPLEMENTED` (`src/vtesbot/cards/forced_confessional.py`,
  `Hook.FORCE_BLOCK_ATTEMPT_FAILURE`/`Hook.INTERCEPT_DECREASE`, tests in
  `tests/cards/test_forced_confessional.py`), its basic clause ("[dom] The
  blocking minion gets -1 intercept") wired against the pre-existing
  `INTERCEPT_DECREASE_HOOK` with a `qualifies` predicate scoped to the one
  specific blocking vampire fixed in context, not a property class (unlike
  Perfect Paragon's own "younger vampires"). Follow-up (`rules-auditor`
  finding on this entry's first landing): the hook was only offered in the
  "block currently succeeds" branch, so the exclusion half of the superior
  clause ("cannot attempt to block this action again") was never reachable
  while a candidate was already failing on the raw numbers -- a legal choice
  silently never offered (CLAUDE.md §5). "Only when needed" (OQ-31/39) scopes
  solely to stealth/intercept *value* modifiers; it does not scope this
  hook's own non-numeric exclusion half, which has nothing to do with the
  current numbers (Rulebook §4 "Resolve Any Block Attempts": a failed
  attempt may be retried "as often as the blocking Methuselah wishes").
  Fixed by also offering `FORCE_BLOCK_ATTEMPT_FAILURE_HOOK` to the actor,
  alone (not merged with any numeric modifier, since none are needed there),
  in the "block currently fails on the raw numbers" branch too, once the
  defender has declined or exhausted `INTERCEPT_MODIFIER_HOOK` -- impulse
  returning to the actor. Proven by `tests/rules/test_force_block_attempt_
  failure.py::test_offered_even_while_already_failing_on_the_raw_numbers`.
