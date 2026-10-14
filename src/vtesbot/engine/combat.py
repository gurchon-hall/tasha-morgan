"""Basic combat: hand strikes only, fixed close range.

Source: Rulebook SS4 Combat (per the `vtes-rules-reference` skill condensed
mapping): "Rounds of 7 steps: before range -> determine range (maneuvers
alternate, no two in a row) -> before strikes -> strike (acting minion
chooses first; simultaneous resolution) -> damage resolution (prevent, then
mend) -> press (alternating) -> end of round. Combat ends at once if a
combatant is no longer ready." "Hand strike = strength (default 1), close
range only."

CLAUDE.md milestone-2 scope restriction: only hand strikes are implemented
(no ranged strikes, no maneuvers/range changes, no equipment/retainers/
allies in combat). Range therefore has nothing to determine this milestone:
combat is fixed at close range by construction (the only range hand strikes
need), and the "before range"/"determine range" steps are no-ops pending a
later milestone that adds ranged weapons and the maneuver mechanic.

Press step order (resolves docs/OPEN_QUESTIONS.md OQ-3): the rulebook states
"The acting minion always gets first opportunity to use cards or effects
before the opposing minion" at every stage of combat, including press (per
`rules-auditor`'s verbatim quote from the primary rulebook text, matching
the project's own impulse invariant, CLAUDE.md SS5 / Rulebook SS2
Sequencing). The acting minion's controller is therefore always asked to
press first, every round, never alternating by round parity.

Combat-card hook wiring (`engine/hooks.py`): the strike step offers each
combatant's controller every registered
`"combat_strike_option"` alongside the two built-in choices (a card-granted
strike option's `apply(state)` must return the damage it inflicts, so it can
fully stand in for a hand strike -- e.g. a card that adds flat damage to a
hand strike); `"combat_strength_modifier"` is a passive, mandatory numeric
hook (CLAUDE.md rule 3 exception) summed into the base hand-strike strength,
for printed vampire abilities that are not a choice (e.g. a flat "+1
strength" line or a clan-conditional combat bonus). With no providers
registered for either hook, every strike is exactly a plain hand strike at
strength 1 -- byte-for-byte the milestone-2 result. Ranged strikes (a strike
usable only at long range) remain out of scope this pass; the Determine
Range step and the maneuver mechanic that moves a round between close and
long range are now built -- see "Determine Range and maneuvers" below.

Dodge and same-round additional strikes (resolves `docs/OPEN_QUESTIONS.md`
OQ-18 Gap 2) -- re-fetched live
<https://www.vekn.net/rulebook/4-detailed-turn-sequence> 2026-10-10, matching
the local cache `data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md`:

- Choose Strike: "Each minion chooses their strike. The strike can be from a
  combat card, from a weapon the minion possesses, by default from a hand
  strike, or can be from any other card providing this minion a strike."
  Dodge is one such card-granted strike, *not* a base option every vampire
  has by default -- there is no printed or rules text granting every minion
  a dodge; it only ever comes from a combat card or a printed ability (e.g.
  Flávio Gonçalves' "special ability to dodge" in the rulebook's own worked
  example). It is therefore wired the same way as `"combat_strike_option"`:
  a hook, `"combat_dodge_option"`, offered alongside it at the strike step,
  with no built-in dodge choice offered when no provider grants one.
- Strike Effects > Dodge: "A dodge strike deals no damage, but it protects
  the dodging minion and their possessions from the effects of the opposing
  strike. ... A dodge is a strike, even though it is solely defensive." The
  engine enforces both halves of this directly, not via a provider's
  `apply` return value: choosing a `"combat_dodge_option"` always deals 0
  damage from that strike, and always zeroes whatever damage the opponent's
  *simultaneous* strike this round would otherwise deal to the dodging
  combatant (`apply(state)` is still invoked, for any of the dodge's own
  side effects, but its return value is ignored for damage purposes).
- Additional Strikes: "Some cards and effects allow a minion to make
  additional strikes during the current round of combat. Additional strikes
  are announced and performed only after the first pair of strikes is
  completed. The acting minion decides whether or not to gain additional
  strikes before the opposing minion, as usual. Additional strikes are
  handled by having another choose strike step and resolve strike step in
  which only the minions with additional strikes may play strike cards. ...
  This is repeated as necessary. A minion cannot use more than one card or
  effect to gain additional strikes per round of combat [the '(limited)'
  card text]." Wired as a second hook, `"combat_additional_strike"`: after
  the normal strike pair (and after each additional-strike pair), the
  acting combatant is asked first, then the other, whether they have and
  want to use a currently-available granted additional strike; a combatant
  who uses one then gets a full, independent strike choice -- the *same*
  `"combat_strike_option"`/`"combat_dodge_option"` machinery as a normal
  strike, never a fixed/hardcoded hand strike (per Choose Strike above, "the
  strike can be from a combat card, ... by default from a hand strike, or
  ... any other card providing this minion a strike" -- nothing in Choose
  Strike or Additional Strikes narrows this for an additional strike) -- and
  the pair (only those who opted in strike; a combatant with no
  available/used additional strike does not strike in that pair) resolves
  the same way, including dodge. The loop repeats "as necessary" (while
  either combatant still has an unused grant), matching the worked example
  (Wauneka 1 additional strike, Flávio Gonçalves 2: two more strike pairs,
  the second with only Flávio striking).

  Cross-card, per-minion "(limited)" cap (OQ-19, `docs/OPEN_QUESTIONS.md`):
  the SS8 rule quoted above is a *cross-card*, round-scoped cap ("a minion
  cannot use more than one card or effect ... per round of combat") -- but
  still strictly per-*minion*: the Wauneka/Flávio Gonçalves worked example
  two paragraphs above is itself two different minions each legally using
  their own additional-strike grant in the *same* round, so the cap must be
  tracked independently per combatant, never pooled jointly. `run_combat`
  creates one fresh, shared `round_state: dict[str, Any]` at the top of
  every round (reset every round) and threads it, under
  `ROUND_STATE_CONTEXT_KEY`, into both `COMBAT_DODGE_OPTION_HOOK`'s and
  `COMBAT_ADDITIONAL_STRIKE_HOOK`'s own hook context -- the two, and only
  two, hooks where a "(limited)" additional-strike grant can originate
  (`COMBAT_STRIKE_OPTION_HOOK`'s plain alternate-strike grants never grant
  an *additional* strike). `additional_strike_limit_used`/`mark_additional_
  strike_limit_used` (below) read/write a flag *keyed by vampire instance
  id* inside that shared dict, never a flat boolean (which would wrongly let
  one combatant's own play block the other's unrelated grant); a card
  module implementing a "(limited)" additional-strike clause (e.g. Dust Up's
  `[cel]`, Side Strike's `[CEL]`) must consult/record it from its own grant
  -- this is what enforces the cap *across* different cards (or a second
  physical copy of the same card) held by the same vampire. Per Dust Up's
  own ruling on where the check belongs ("you cannot play it for the dodge
  only if you already played it for a (limited) additional strike this
  round" [ANK 20220204]), the check gates the *granting* clause itself (a
  dodge-bundled grant counts identically to a direct one), not the later act
  of claiming an already-recorded grant. See `additional_strike_limit_
  used`'s own docstring for the *exempt*-clause boundary (e.g. a future
  Quickness/Hell-for-Leather additional strike that does not count against
  the limit).

With no providers registered for either hook, no dodge/additional-strike
choice is ever offered and the additional-strike loop exits immediately.

Dodge-proof strikes: the Golden Rule for Cards (CLAUDE.md SS2 / Rulebook SS3
"whenever the cards contradict the rules, the cards take precedence") lets a
specific strike's own printed text override the normal dodge rule for that
strike only --
Dust Up's own `[ani]` clause ("This strike cannot be dodged") is the sourced
example, confirmed by its own ruling: "[ani] Does not prevent the opponent
from dodging, the dodge just has no effect." [LSJ 20030902-2] [LSJ
20060808-1] -- i.e. the opponent may still *choose* to dodge (dodge remains
a real, always-available-when-granted strike choice), but that dodge has
*zero effect* against this one, specifically-flagged strike; the dodging
combatant's own simultaneous strike against the attacker (if any) is
unaffected -- dodge-proof only cancels the *protection* dodge would
otherwise have granted against this strike, never the dodging combatant's
own offense. A `combat_strike_option` provider signals this by returning a
`StrikeDamage(amount, ignore_dodge=True)` from `apply(state)` instead of a
plain `int` (the common case; a plain `int` behaves exactly like
`StrikeDamage(amount, ignore_dodge=False)`); the built-in hand strike and
`combat_dodge_option` itself never need this (hand strike is always
dodgeable by rule default; a dodge strike deals no damage regardless).

Determine Range and maneuvers (Saku Pihlajamäki, 201658, "Anarch Baron of
Helsinki: Saku gets 1 optional maneuver each combat" -- the first card in
the pool needing it) -- re-fetched live
<https://www.vekn.net/rulebook/4-detailed-turn-sequence> 2026-10-11,
matching the local cache `data/sources/rulebook/2026-10-09/
4-detailed-turn-sequence.md`:

- Combat Sequence (verbatim, step list): "1. Before Range: Play cards before
  range is chosen. 2. Determine Range: Use maneuvers to change the range to
  close or long. 3. Before Strikes ... 4. Strike ... 5. Damage Resolution ...
  6. Press ... 7. End of Round ... The acting minion always gets first
  opportunity to use cards or effects before the opposing minion at every
  stage of combat." The last sentence is the same text OQ-3 already quotes
  for the press step; it applies identically here, so the acting combatant's
  controller is offered the first maneuver-or-decline turn of every round,
  same precedent as press.
- Determine Range (verbatim): "Each round of combat is fought at either
  close range or long range. Close range is the default for each round. ...
  A minion in combat can use a maneuver to get to long range, or they can
  maneuver to get back to close range if their opponent maneuvers to long.
  The two combatants can continue playing maneuvers to keep offsetting the
  effects of their opponent's last maneuver for as long as they wish. A
  minion cannot play two maneuvers in a row, which would effectively cancel
  each other. ... If a combat card played by a minion has an 'optional
  maneuver' as part of the effect, then the minion may decline to use the
  maneuver." `run_combat` now runs this as its own step, `_determine_range`,
  immediately before the strike step every round, matching the rulebook's
  own step-2-before-step-4 ordering.
- Turn order and termination: NOT `hooks.resolve_impulse_window`'s "impulse
  returns to the acting Methuselah" model -- that model would offer the same
  combatant a second, consecutive turn the instant they maneuver, directly
  contradicting "A minion cannot play two maneuvers in a row." Instead,
  `_determine_range` runs its own strict turn-by-turn alternation (acting
  combatant's controller first, then strictly the other combatant every
  single turn after, win or decline -- never the same combatant twice in a
  row by construction, so the "no two in a row" rule is enforced by the loop
  shape itself, with no provider-side check needed), closing once two
  consecutive turns both decline/have nothing available (CLAUDE.md rule 4's
  "the window closes when both pass," applied turn-by-turn here rather than
  side-by-side since the two combatants are never offered simultaneous turns
  in this step). `_ask_maneuver` offers every registered `"maneuver"` option
  (`cards/registry.py::Hook.MANEUVER`) plus a decline choice; no options
  registered => no `Decision` raised at all for that turn (CLAUDE.md "only
  when needed"), so with no `"maneuver"` provider registered anywhere, both
  of the two required turns are silent no-ops and `state.combat_range` stays
  `CLOSE_RANGE` for the whole round -- byte-for-byte the previous
  (pre-maneuver) result; no existing test's script needed a new entry.
  Reproduces the module's own worked example verbatim (`tests/rules/
  test_combat_maneuver.py::test_ayelech_colette_worked_example`): Colette
  (acting) declines first; Ayelech (blocking) maneuvers to long; Colette
  maneuvers back to close; Ayelech maneuvers again to long; Colette has
  nothing left and declines; the implicit sixth turn (Ayelech, now also with
  nothing left) is the second consecutive decline that closes the step with
  the range left at long -- the worked example's own prose elides this last,
  trivial turn, but the loop still asks it (a provider legitimately could
  have one more grant to offer there; this combat's fake providers do not).
- Scope restriction, first pass (superseded below for the strike-bundled
  case -- OQ-28, `docs/OPEN_QUESTIONS.md`, resolved): only an ability-granted
  maneuver *not* bundled with choosing a strike was wired at first -- exactly
  Saku's shape (a printed vampire ability, "1 optional maneuver each combat,"
  no card played, not bundled with a strike choice). Pursuit's own basic
  `[cel]` "Maneuver." clause (`cards/pursuit.py`, OQ-27, resolved) was later
  confirmed to be this same plain shape too, despite being a played card, not
  a printed ability -- see that module's own docstring for the full
  Choose-Strike-citation analysis distinguishing a bare "Maneuver." clause
  from a maneuver genuinely "from a strike."

Maneuver bundled with a strike (resolves OQ-28, `docs/OPEN_QUESTIONS.md` --
Slam, krcg id 101798, "[pot] Strike: hand strike at +2 damage. [POT] As
above, with 1 optional maneuver, only usable to get to close range."; .44
Magnum, krcg id 100001, is the identically-shaped weapon-side example, not
yet in the card pool): Rulebook SS4 Combat > Strike > Choose Strike
(verbatim, re-fetched live <https://www.vekn.net/rulebook/4-detailed-turn-sequence>
2026-10-12, matching the local cache `data/sources/rulebook/2026-10-09/
4-detailed-turn-sequence.md`): "Each minion chooses their strike. The strike
can be from a combat card, from a weapon the minion possesses, by default
from a hand strike, or can be from any other card providing this minion a
strike. If a minion has used a maneuver from a strike (either a strike card
or a weapon) this round, then they cannot choose any other strike for their
initial strike of the round." Also Determine Range itself: "To use a
maneuver from a strike card, the minion plays the strike card during this
step instead of during the choose strike step. If a minion uses the maneuver
from a strike card or a weapon, they are effectively choosing their strike as
well." Together these mean: claiming this kind of `MANEUVER_HOOK` grant does
not just flip the range -- it *simultaneously* fixes that combatant's one
strike choice for the round to the same bundled strike effect, so `_ask_
strike` must never separately offer that combatant a strike choice for their
initial strike afterwards.

Mechanism: `_ask_maneuver`'s `hooks.offer(MANEUVER_HOOK, ...)` call now also
threads the current round's shared scratch dict into the hook context under
`round_state=` (`ROUND_STATE_CONTEXT_KEY`) -- the same key/object `COMBAT_
DODGE_OPTION_HOOK`/`COMBAT_ADDITIONAL_STRIKE_HOOK` already receive it under
(module docstring's "Cross-card '(limited)' cap" section); `run_combat`
therefore now creates `round_state` once at the very top of each round
iteration, *before* calling `_determine_range`, rather than only afterwards
(reordered; no other call site's shape changes). A `MANEUVER_HOOK` provider
whose own grant is itself part of a strike effect calls `commit_strike_for_
round(context, strike)` (below) from the very closure that applies the
maneuver, passing a `HookOption` wrapping that bundled strike's own effect
(the same `apply(state) -> int | StrikeDamage` contract a `COMBAT_STRIKE_
OPTION_HOOK` provider uses) -- this records the commitment under `COMMITTED_
STRIKE_KEY` inside `round_state`, keyed by vampire instance id. `_ask_strike`
consults (and consumes) that record for `vampire.instance_id` before
offering anything: if present, it resolves straight to the pre-committed
strike, with no `Decision` raised for that combatant's initial strike at all
-- not "may also choose this strike," but exactly "this strike card is
played now, during Determine Range, instead of during the choose strike
step." Popping the entry on read (rather than merely reading a flag) is what
correctly scopes the lock to "their initial strike of the round" only: the
first, and only the first, `_ask_strike` call for that vampire each round
finds it; any later Additional Strikes pair (Rulebook SS4 Combat > Additional
Strikes, a separate, later choose-strike step the quoted restriction's own
"initial strike" wording does not reach) finds nothing and gets the engine's
normal, fully independent strike choice, exactly like any other combatant.
A plain maneuver not bundled with a strike (Saku, Pursuit's basic clause,
Dance with the Devil, Fleetness) must never call `commit_strike_for_round` --
doing so would wrongly lock that combatant's strike choice with no textual
basis. Wiring an actual card (Slam, .44 Magnum) against this mechanism is
left to a future `card-implementer` pass; this pass only builds and tests the
generic engine mechanism (CLAUDE.md "decision points, not hard-coded play" /
"card hooks" -- the engine must not special-case a card name).
- Per-combat, not per-round, scoping: Saku's own grant ("1 optional maneuver
  each combat") spans however many rounds the whole combat lasts, unlike a
  combat card's maneuver grant (consumed the one round it is played, same
  round-scoped lifetime as `ROUND_STATE_CONTEXT_KEY`). `run_combat` creates
  one fresh `combat_state: dict[str, Any]` once, *outside* the per-round
  `while` loop (never recreated between rounds of the same combat, unlike
  `round_state`), and threads it into `"maneuver"`'s hook context under
  `COMBAT_STATE_CONTEXT_KEY` -- a future Saku module stores its own
  "used this combat" flag inside it (e.g. keyed by `context["vampire"]`,
  the same per-vampire-id convention `ADDITIONAL_STRIKE_LIMIT_KEY` already
  uses, to stay correct if a future card grants a second, independent
  vampire's own per-combat maneuver too), exactly mirroring `round_state`'s
  shape but with a combat-length, not round-length, lifetime.
- `GameState.combat_range` (`engine/state.py`) is set to `CLOSE_RANGE` at
  the top of `_determine_range` ("Close range is the default for each
  round") and flipped on every maneuver played, so it always reflects the
  range as determined *so far* this round; reset to `None` once `run_combat`
  itself returns (no combat in progress). Range-gating a strike or other
  strike-resolution-step effect by close/long ("Some effects can only be
  used at close range, some only at long range") is explicitly **not**
  built this pass (point 6 of this task's scope) -- no implemented card
  needs it yet; `GameState.combat_range` is exposed precisely so a later
  pass can read it without an engine signature change, not to pre-build the
  gating itself.

Known future gap (deliberately not built -- no card in the current pool's
classification needs it, milestone-2 scope is hand-strikes-only): dodge as
implemented here only nullifies numeric *damage*. Strike Effects > Dodge
protects from "the effects of the opposing strike" more broadly (e.g. a
future Steal Blood-style strike's non-damage effect); `_resolve_one_strike`
currently has no mechanism to suppress a non-damage `apply(state)` side
effect for a dodging combatant. A future combat card needing this will need
to extend `COMBAT_STRIKE_OPTION_HOOK`'s contract again.

Pre-combat grant seeding (OQ-25, `docs/OPEN_QUESTIONS.md`, resolved -- Fleetness
(100747), "This acting vampire gets 1 optional maneuver during that combat"):
a grant that must exist *before* `run_combat` itself is ever called (the
acting vampire's own card is played, and the grant fixed, at Rulebook SS4
"Announce the Action" time -- strictly before the block-attempt window even
opens, let alone whichever combat results from it) cannot be recorded the way
Saku Pihlajamäki's own "1 optional maneuver each combat" is (entirely inside
`combat_state`, which `run_combat` previously always created fresh and empty,
with no way for an earlier caller to seed it). `run_combat` now accepts an
optional `initial_combat_state: dict[str, Any] | None = None` parameter, used
directly (not copied) as its local `combat_state` instead of always starting
from `{}`; a caller with nothing to pre-seed (every call site before this
pass) passes nothing and sees byte-for-byte the previous `{}`-start
behaviour. `PRE_COMBAT_MANEUVER_GRANT_KEY` is the generic (not
Fleetness-specific) key this seed is recognized under, nested inside
`combat_state` exactly like Dust Up's own `CEL_GRANTS_KEY` (module docstring's
"Cross-card '(limited)' cap" section) and Saku's own per-combat "used" flag --
a `dict[str, int]` keyed by vampire instance id, each entry counting that
vampire's still-unclaimed pre-granted maneuvers (an `int` count, not a bool,
so a future card printing more than one pre-combat maneuver -- or two
different pre-combat-granting cards stacking on the same vampire -- composes
correctly by addition rather than one silently overwriting the other).
`seed_pre_combat_maneuver_grant`/`pre_combat_maneuver_available`/
`consume_pre_combat_maneuver_grant` below are the shared helpers: a card's own
`"maneuver"` hook provider calls `pre_combat_maneuver_available(context)` at
offer time and `consume_pre_combat_maneuver_grant(context)` from the option it
offers, exactly mirroring `additional_strike_limit_used`/`mark_additional_
strike_limit_used`'s own degrade-gracefully contract (a hook offered directly,
bypassing `run_combat`, with no `combat_state` in its context at all, is
treated as "nothing granted" rather than raising).

Two distinct call sites now have somewhere to put this pre-seed: (1) an
unblocked action's own `resolve()` callback, which already calls `run_combat`
directly (mirrors `cards/line_brawl.py`'s `[pot]` clause), can now pass
`initial_combat_state=seed_pre_combat_maneuver_grant(acting_vampire_id)`
itself -- no further engine change needed for this path, since the card's own
closure already has full control over that call; (2) a *blocked* action's
combat is run by `engine/action.py::perform_minion_action` itself, internally
-- see that module's own docstring and `engine/phases/minion.py::
ActionCardSpec.maneuver_grant` for how this same seed now reaches that
internal call too.

End of Round and round-scoped blood-loss tracking (OQ-29, `docs/
OPEN_QUESTIONS.md` -- Taste of Vitae, krcg id 101945, "Only usable at the end
of a round of combat. ... This vampire gains blood equal to the amount of
blood lost by the opposing vampire to damage this round."):

- Combat Sequence (verbatim, step list, quoted in full above in "Determine
  Range and maneuvers"): "... 6. Press ... 7. End of Round: End of round
  cards and effects are played here." `run_combat`'s own round loop
  previously had no such step: every exit from a round's own processing --
  the normal end (nobody presses), a premature end (a combatant goes
  not-ready before the Press step is even reached, Rulebook SS4: "Combat
  ends at once if a combatant is no longer ready"), and the "someone
  presses, another round follows" case -- left with no hook offer of any
  kind. Taste of Vitae's own rulings confirm this window exists
  independently of whether Press itself ever actually ran: "Must be played
  after the presses are handled and can be played if the round ends
  prematurely" [RTR 20001020] [LSJ 20001024] [RTR 20030519], and "Can be
  played if the opponent was burned" [LSJ 20031201-2].
- `run_combat`'s round loop is restructured (behaviour-preserving for every
  existing test: with no `END_OF_ROUND_HOOK` provider registered, `hooks.
  resolve_impulse_window` returns immediately with no `Decision` raised,
  CLAUDE.md "only when needed") around two local booleans, `still_ready`
  (did both combatants remain ready through the initial strike pair and any
  additional-strikes pairs) and `pressed` (did either side press -- only
  ever asked if `still_ready`) -- replacing the previous scattered `break`
  statements with a single, unconditional call to `_ask_end_of_round` placed
  once per round, after where the Press step sits in the rulebook's own
  numbering (whether or not Press actually ran this round), immediately
  followed by the loop's own `if not still_ready or not pressed: break`.
  This guarantees exactly one `END_OF_ROUND_HOOK` dispatch per round, on
  every exit path, with no duplicate/missing call possible by construction.
- `_ask_end_of_round` dispatches `END_OF_ROUND_HOOK` via `hooks.
  resolve_impulse_window` (CLAUDE.md rule 4 / Rulebook SS2 Sequencing) --
  acting combatant's controller offered first, matching the Press step's own
  ordering precedent (OQ-3 above), but using the full two-sided
  "impulse-returns-to-the-acting-Methuselah, closes on two consecutive
  passes" shape rather than `_ask_press`'s own narrower "ask once per side,
  first yes wins" shape, since an end-of-round card is a real window where
  either side may act (and re-act) any number of times -- not a single
  binary decision. Context carries `acting_player`/`acting_vampire`/
  `blocking_player`/`blocking_vampire` (plain `str` ids, never the live
  object -- `Decision.context` reaches agent-visible code, CLAUDE.md
  "information hiding") so a provider can tell, from `context["player"]`
  alone, which side is its own controller and which vampire is "this
  vampire" versus "the opposing vampire" for a card like Taste of Vitae; and
  `round_state=` (`ROUND_STATE_CONTEXT_KEY`), the same shared, round-scoped
  scratch dict already threaded into every other combat hook this round, so
  a provider can also read this round's blood-loss record (below) before it
  is discarded at the top of the next round.
- Blood-loss tracking: Taste of Vitae's own gain amount is "the amount of
  blood lost by the opposing vampire to damage this round" -- not the
  vampire's current blood deficit (which could also reflect an unrelated
  blood/pool-moving effect played the same turn) and not the raw damage
  dealt (unmended normal damage left as `wounded` costs no blood at all;
  mended normal damage costs exactly 1 blood per point actually mended, a
  player's own choice at the Mend step; aggravated damage against an
  already-wounded vampire burns 1 blood per point only while blood remains,
  then burns the vampire outright with no further blood cost once it runs
  out). `engine/damage.py::apply_damage` now accepts an optional
  `round_state: dict[str, Any] | None = None` parameter -- `_resolve_strike_
  pair` (the only call site inside a combat) passes the current round's
  shared scratch dict; every other existing call site (direct card effects,
  scenario tests) passes nothing and sees byte-for-byte the previous,
  untracked behaviour. When given, `apply_damage` records exactly the
  amount `vampire.blood` decreased from its own mend step and its own
  aggravated-burn step (and only those two branches -- nothing else in that
  function decreases blood) into the dict under `engine/damage.py::
  BLOOD_LOST_TO_DAMAGE_KEY`, keyed by vampire instance id (mirrors every
  other per-vampire-id-keyed sub-dict this module's own `round_state`
  already carries). `engine/damage.py::blood_lost_to_damage_this_round` is
  the public helper a future provider (Taste of Vitae) queries, analogous to
  `additional_strike_limit_used`/`commit_strike_for_round`'s own
  public-helper shape -- it lives in `engine/damage.py`, not here, and takes
  the raw `round_state` dict directly (not a hook `context` mapping) to
  avoid a circular import (`engine/combat.py` already imports `apply_damage`
  from `engine/damage.py`); a provider reads `context.get(ROUND_STATE_
  CONTEXT_KEY)` itself (the same pattern `cards/dust_up.py`'s own
  `_round_state` helper already uses) and passes the result in. The record
  is a plain dict entry keyed by instance id, untouched by any zone
  transition, so it remains fully readable after the tracked vampire is
  burned -- directly supporting "Can be played if the opponent was burned"
  [LSJ 20031201-2].
- Wiring an actual card (Taste of Vitae) against `END_OF_ROUND_HOOK`/
  `blood_lost_to_damage_this_round` is left to a future `card-implementer`
  pass (OQ-29); this pass only builds and tests the two generic engine
  mechanisms (CLAUDE.md "decision points, not hard-coded play" / "card
  hooks" -- the engine must not special-case a card name).

Before Range (resolves OQ-47, `docs/OPEN_QUESTIONS.md` -- Weighted Walking
Stick, krcg id 102169, "Only usable before range is determined during the
first round. Put this card with 5 counters on it on this minion; it becomes
a melee weapon equipment that can strike: strength+1 damage. For each damage
inflicted by this strike (even if prevented), burn 1 counter from this
card."):

- Combat Sequence step 1 (verbatim, quoted in full above in "Determine Range
  and maneuvers"): "1. Before Range: Play cards before range is chosen." --
  distinct from, and strictly before, step 2 "Determine Range" (maneuvers,
  already built). `run_combat` previously had no call site for this step at
  all (this module's own earlier docstring said as much: "the 'before
  range'/'determine range' steps are no-ops"); step 2 was since built, this
  step was not.
- `BEFORE_RANGE_HOOK` is offered exactly once per *combat*, immediately
  before round 1's own Determine Range step -- never again in a later round
  of the same combat, even if pressing continues it: "before range is
  determined during the first round" is a one-shot, whole-combat window, not
  a per-round one, unlike every other hook this module wires (`MANEUVER_
  HOOK`/`COMBAT_STRIKE_OPTION_HOOK`/etc., all re-offered every round).
  `run_combat` tracks this with a single local `before_range_offered: bool`,
  set once the window has run, checked at the top of every round iteration
  before `_determine_range` -- mirrors the "guard a one-shot window inside a
  loop" shape, simpler than `END_OF_ROUND_HOOK`'s own per-round dispatch
  since there is no "exit path" subtlety here: the window only ever needs to
  run once, at the very first opportunity, and every combat reaches round 1
  by construction (a combat is only ever started once a block has already
  succeeded, so both combatants are already `"ready"` by the time
  `run_combat` is called).
- `_ask_before_range` dispatches `BEFORE_RANGE_HOOK` via `hooks.
  resolve_impulse_window` -- the same two-sided, repeatable "impulse returns
  to the acting Methuselah, closes on two consecutive passes" shape
  `_ask_end_of_round` already uses (CLAUDE.md rule 4 / Rulebook SS2
  Sequencing), not `_ask_press`'s narrower single-binary-choice shape, since
  Combat Sequence step 1 is a real window where either combatant's
  controller may play an arbitrary number of "before range" cards. Acting
  combatant's controller is offered first, the same ordering precedent as
  Press/End of Round/Determine Range (OQ-3, module docstring). Context
  carries `acting_player`/`acting_vampire`/`blocking_player`/
  `blocking_vampire` (plain `str` ids, never the live object -- CLAUDE.md
  "information hiding", same convention as `_ask_end_of_round`'s own
  context) -- no `round_state`/`combat_state` key, since this window runs
  strictly *before* `run_combat`'s per-round `round_state` for round 1 is
  even created, and no known card needing this step needs anything
  combat-scoped either.
- A provider's own `apply(state)` is free to look up either combatant's
  `VampireInPlay` (via the context ids above) and attach a card directly --
  e.g. `engine.attachments.attach_card`/a direct `engine.cards.
  CardAttachment(...)` construction (mirrors `cards/celerity.py`'s own
  non-unique-attachment pattern: Weighted Walking Stick's own printed text
  carries no "Unique" marker, so a future card module may construct it
  exactly the same way, with an initial `counters=5`). The *strike* half of
  Weighted Walking Stick (a melee weapon strike at strength+1, burning one
  attachment counter per point of damage inflicted even if prevented) needs
  no change to `COMBAT_STRIKE_OPTION_HOOK`'s existing contract at all: that
  hook's own provider `apply(state)` already returns the pre-prevention,
  post-reduction damage amount (this module's own "Combat-card hook wiring"
  section above), which is exactly the quantity "for each damage inflicted
  by this strike (even if prevented)" needs -- a future provider decrements
  `min(amount, counters)` off its own attachment inside that same `apply`
  and removes the attachment once its `counters` reaches 0, entirely within
  its own card module, with no engine-side involvement.
- With no `BEFORE_RANGE_HOOK` provider registered (every existing test, and
  every other card in the pool today), `hooks.resolve_impulse_window`
  returns immediately with no `Decision` ever raised (CLAUDE.md "only when
  needed") -- byte-for-byte the previous, no-op-step result.
- Wiring an actual card (Weighted Walking Stick) against this hook is left
  to a future `card-implementer` pass (OQ-47); this pass only builds and
  tests the generic engine mechanism.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import hooks
from .damage import apply_damage
from .decision import Choice, Decision
from .pool import simultaneous_pool_losses

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

HAND_STRIKE_STRENGTH = 1
HAND_STRIKE_VALUE = "hand_strike"
NO_STRIKE_VALUE = "no_strike"
"""The two built-in `strike_choice` values `_ask_strike` always offers
(Rulebook SS4 Combat > Strike, "by default from a hand strike"). Named here
(rather than left as bare string literals at each use site) so
`commit_strike_for_round` can assert no card-sourced choice value collides
with either -- a collision would silently mis-resolve `_resolve_one_strike`'s
own `if choice == ...` branching onto the wrong effect, exactly the "never
mis-resolves a card" failure CLAUDE.md forbids."""
COMBAT_STRIKE_OPTION_HOOK = "combat_strike_option"
COMBAT_STRENGTH_MODIFIER_HOOK = "combat_strength_modifier"
COMBAT_DODGE_OPTION_HOOK = "combat_dodge_option"
COMBAT_ADDITIONAL_STRIKE_HOOK = "combat_additional_strike"
MANEUVER_HOOK = "maneuver"
"""Matches `cards/registry.py::Hook.MANEUVER`'s string value -- see module
docstring's "Determine Range and maneuvers" section."""
END_OF_ROUND_HOOK = "end_of_round"
"""Matches `cards/registry.py::Hook.END_OF_ROUND`'s string value -- see
module docstring's "End of Round and round-scoped blood-loss tracking"
section (OQ-29, `docs/OPEN_QUESTIONS.md`)."""
BEFORE_RANGE_HOOK = "before_range"
"""Matches `cards/registry.py::Hook.BEFORE_RANGE`'s string value -- see
module docstring's "Before Range" section (OQ-47, `docs/OPEN_QUESTIONS.md`,
resolved)."""

CLOSE_RANGE = "close"
LONG_RANGE = "long"
"""The two legal values of `GameState.combat_range` (Rulebook SS4 Combat >
Determine Range: "Each round of combat is fought at either close range or
long range")."""

ROUND_STATE_CONTEXT_KEY = "round_state"
"""Context key, under `COMBAT_DODGE_OPTION_HOOK`/`COMBAT_ADDITIONAL_STRIKE_
HOOK`/`MANEUVER_HOOK`, for the shared, round-scoped scratch `dict[str, Any]`
`run_combat` creates fresh at the top of every round (see module docstring's
"Cross-card '(limited)' cap" and "Maneuver bundled with a strike" sections).
`MANEUVER_HOOK` only started receiving this context key alongside the other
two once `commit_strike_for_round`/`COMMITTED_STRIKE_KEY` (below) needed
somewhere round-scoped to record a strike-bundled maneuver's commitment --
earlier callers of `MANEUVER_HOOK` that never consult it are unaffected. A
hook offered directly, bypassing `run_combat` (as several scenario tests do,
to probe one hook in isolation), simply has no entry under this key;
`additional_strike_limit_used`/`mark_additional_strike_limit_used`/
`commit_strike_for_round` below all treat that as "no shared state available"
and degrade gracefully (see their own docstrings) rather than raising."""

COMBAT_STATE_CONTEXT_KEY = "combat_state"
"""Context key, under `MANEUVER_HOOK`, for the shared, *combat*-scoped (not
round-scoped -- see `ROUND_STATE_CONTEXT_KEY` above and the module
docstring's "Determine Range and maneuvers" section) scratch `dict[str, Any]`
`run_combat` creates once, before its per-round `while` loop, and never
recreates between rounds of the same combat -- unlike `round_state`, which is
fresh every round. A provider for a once-per-*combat* grant (e.g. Saku
Pihlajamäki's printed "1 optional maneuver each combat") records its own
"used" flag inside this dict (by convention keyed by `context["vampire"]`,
the same per-vampire-id pattern `ADDITIONAL_STRIKE_LIMIT_KEY` uses, so one
combatant's own per-combat grant never blocks the other's); no generic
engine-level helper is provided for this (unlike `additional_strike_limit_
used`/`mark_additional_strike_limit_used` below), since no cross-card,
engine-enforced cap is sourced for maneuvers -- it is a single card's own
private bookkeeping, not a rule this module itself needs to enforce."""

PRE_COMBAT_MANEUVER_GRANT_KEY = "pre_combat_maneuver_grants"
"""Key inside the `combat_state` dict (`COMBAT_STATE_CONTEXT_KEY`) for a
pre-combat maneuver grant seeded via `run_combat`'s own `initial_combat_state`
parameter (module docstring's "Pre-combat grant seeding" section, OQ-25,
`docs/OPEN_QUESTIONS.md`). Value is a `dict[str, int]` keyed by vampire
instance id, each entry counting that vampire's still-unclaimed pre-granted
maneuvers -- generic (not Fleetness-specific), exactly the "documented
key/shape a `'maneuver'` hook provider can recognize" OQ-25 asked for. A
`"maneuver"` hook provider recognizing this key must consume (decrement) its
own vampire's entry when it offers/claims the grant -- use
`pre_combat_maneuver_available`/`consume_pre_combat_maneuver_grant` below
rather than reading/writing this dict directly, mirroring `additional_
strike_limit_used`/`mark_additional_strike_limit_used`'s own shared-helper
convention."""


def seed_pre_combat_maneuver_grant(vampire_id: str, count: int = 1) -> dict[str, Any]:
    """Build an `initial_combat_state` seed (`run_combat`'s own parameter)
    granting `vampire_id` `count` unclaimed pre-combat maneuvers (default 1),
    recognized by `pre_combat_maneuver_available`/`consume_pre_combat_
    maneuver_grant` below via `PRE_COMBAT_MANEUVER_GRANT_KEY`. A card whose
    own text grants a pre-combat maneuver calls this to build the dict it
    passes as `run_combat(..., initial_combat_state=...)` (unblocked path) or
    as `ActionCardSpec.maneuver_grant`/`perform_minion_action`'s own
    `maneuver_grant` argument (blocked path, `engine/action.py`,
    `engine/phases/minion.py`) -- the single source of truth for this seed's
    shape, so a producing card module and a consuming `"maneuver"` provider
    cannot silently desync over a hand-rolled dict literal."""
    return {PRE_COMBAT_MANEUVER_GRANT_KEY: {vampire_id: count}}


def pre_combat_maneuver_available(context: Mapping[str, Any]) -> bool:
    """Whether `context["vampire"]` currently has an unclaimed pre-combat
    maneuver grant (module docstring's "Pre-combat grant seeding" section). A
    missing `COMBAT_STATE_CONTEXT_KEY` entry (the hook offered directly,
    bypassing `run_combat` -- some scenario tests do this to probe a provider
    in isolation) is treated as "nothing granted," matching `additional_
    strike_limit_used`'s own degrade-gracefully convention."""
    combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
    if combat_state is None:
        return False
    return combat_state.get(PRE_COMBAT_MANEUVER_GRANT_KEY, {}).get(context["vampire"], 0) > 0


def consume_pre_combat_maneuver_grant(context: Mapping[str, Any]) -> None:
    """Consume one of `context["vampire"]`'s unclaimed pre-combat maneuver
    grants (see `pre_combat_maneuver_available`). A missing `COMBAT_STATE_
    CONTEXT_KEY` entry, or a vampire with none left, is a no-op."""
    combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
    if combat_state is None:
        return
    grants = combat_state.get(PRE_COMBAT_MANEUVER_GRANT_KEY, {})
    vampire_id = context["vampire"]
    if grants.get(vampire_id, 0) > 0:
        grants[vampire_id] -= 1


ADDITIONAL_STRIKE_LIMIT_KEY = "additional_strike_limit_used"
"""Key inside the `ROUND_STATE_CONTEXT_KEY` dict for the "(limited)"
additional-strike flag (SS8 glossary / module docstring: "A minion cannot
use more than one card or effect to gain additional strikes per round of
combat"). The cap is per-*minion*, not joint across the whole fight (SS8's
own wording: "a minion cannot ... per round of combat", not "the
combatants"; the Wauneka/Flávio Gonçalves worked example quoted earlier in
this module's own docstring has *two different minions* each legally using
their own additional-strike grant in the *same* round) -- so the value
stored under this key is a `dict[str, bool]` keyed by vampire instance id
(`context["vampire"]`), one independent flag per combatant, *not* a single
shared boolean. `round_state` itself is still one object shared by both
combatants' hook calls each round (`run_combat` passes the identical dict
regardless of which combatant is being asked), so a flat, un-keyed boolean
here would wrongly let one combatant's own "(limited)" play block the
*other*, unrelated combatant's own, independent grant for the rest of the
round -- exactly the per-vampire-id-keyed pattern `cards/dust_up.py`'s own
`CEL_GRANTS_KEY` already uses for its own, narrower, per-card state."""


def additional_strike_limit_used(context: Mapping[str, Any]) -> bool:
    """Whether *this combatant* (`context["vampire"]`) has already used a
    non-exempt "(limited)" additional-strike grant this round (see module
    docstring's "Cross-card '(limited)' cap" section; SS8 glossary quoted
    there, and `ADDITIONAL_STRIKE_LIMIT_KEY`'s own docstring on why this is
    per-vampire, not joint across both combatants). A card module
    implementing a "(limited)" clause (e.g. Dust Up's `[cel]`, Side Strike's
    `[CEL]`) must call this from its own grant's `offer`-time gate, before
    adding itself to the choices a hook call returns -- per Dust Up's own
    ruling ("you cannot play it for the dodge only if you already played it
    for a (limited) additional strike this round" [ANK 20220204]), the check
    belongs at the *granting* clause, not at the later act of claiming an
    already-recorded grant.

    A card module implementing an *exempt* clause per its own printed text
    (e.g. a future Quickness `[CEL]`/Hell-for-Leather `[cel]` "additional
    strike that does not count against the limit") must never call this (or
    `mark_additional_strike_limit_used`) for that clause -- calling either
    out of copy-paste habit from a "(limited)" clause would silently defeat
    the card's own printed exemption, with no test failure to catch it; the
    exemption is convention-only, not enforced by this function.

    A missing `ROUND_STATE_CONTEXT_KEY` entry (no shared container threaded
    in -- e.g. a hook offered directly in a unit test that only probes one
    call in isolation) is treated as "not used yet": there is nothing to
    persist across separate calls in that case, so the only correct answer
    for a single, isolated offer is the common not-yet-played case. A test
    that needs to prove the cap persists *across* separate calls must
    construct its own shared dict and pass it as
    `round_state=...` to each call, exactly as `run_combat` does across a
    real round.
    """
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if round_state is None:
        return False
    return bool(round_state.get(ADDITIONAL_STRIKE_LIMIT_KEY, {}).get(context["vampire"]))


def mark_additional_strike_limit_used(context: Mapping[str, Any]) -> None:
    """Record that *this combatant* (`context["vampire"]`) has used a
    non-exempt "(limited)" additional-strike grant this round -- see
    `additional_strike_limit_used`, including its warning that an *exempt*
    clause must never call this (calling it anyway would silently defeat
    that clause's own printed exemption, with no test to catch it). A
    missing `ROUND_STATE_CONTEXT_KEY` entry is a no-op (nothing to persist
    to, same degrade-gracefully reasoning as `additional_strike_limit_
    used`)."""
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if round_state is not None:
        round_state.setdefault(ADDITIONAL_STRIKE_LIMIT_KEY, {})[context["vampire"]] = True


@dataclass(frozen=True)
class StrikeDamage:
    """Richer return shape for a `COMBAT_STRIKE_OPTION_HOOK` provider's
    `apply(state)`, for a strike that needs to flag itself dodge-proof (see
    module docstring). `amount` is the damage this strike inflicts, exactly
    like the plain-`int` contract; `ignore_dodge=True` means the opponent's
    dodge (if chosen) has no effect against this specific strike.
    """

    amount: int
    ignore_dodge: bool = False


COMMITTED_STRIKE_KEY = "committed_strike"
"""Key inside the `ROUND_STATE_CONTEXT_KEY` dict for a strike effect a
`MANEUVER_HOOK` grant has pre-committed a combatant to for their *initial*
strike of the round (module docstring's "Maneuver bundled with a strike"
section, OQ-28 `docs/OPEN_QUESTIONS.md`; Rulebook SS4 Combat > Strike >
Choose Strike: "If a minion has used a maneuver from a strike ... this
round, then they cannot choose any other strike for their initial strike of
the round"). Value is a `dict[str, hooks.HookOption]` keyed by vampire
instance id -- per-combatant, like every other `round_state` sub-dict in
this module, since the two combatants' commitments (if any) are entirely
independent of each other. `_ask_strike` pops (not just reads) its own
combatant's entry the first time it is consulted each round: only that
first lookup is the combatant's "initial strike of the round" the rulebook
text scopes this lock to -- any later Additional Strikes pair (a separate,
later choose-strike step) finds nothing left and gets a full, independent
strike choice, exactly like any other combatant's additional strike.

An entry present under this key for a given vampire id, for as long as it
has *not yet* been popped by `_ask_strike`, doubles as this round's "already
committed a strike-bundled maneuver" flag -- `strike_committed_this_round`
reads it for exactly this purpose. Since Determine Range always runs to
completion before the strike step begins each round (`run_combat`'s own
per-round ordering), this flag is live for the *entire* window during which
a second strike-bundled maneuver could legally be offered, and is gone
(popped) only once that window has already irreversibly closed -- so reusing
this one dict for both purposes, rather than keeping a second explicit
"used" flag, loses no coverage."""


def strike_committed_this_round(context: Mapping[str, Any]) -> bool:
    """Whether `context["vampire"]` already has a strike-bundled-maneuver
    commitment recorded this round (`COMMITTED_STRIKE_KEY`'s own docstring).

    Rulebook SS4 Combat > Determine Range (module docstring's "Maneuver
    bundled with a strike" section, OQ-28 `docs/OPEN_QUESTIONS.md`): "If a
    minion uses the maneuver from a strike card or a weapon, they are
    effectively choosing their strike as well. As such, they cannot use a
    second strike card or weapon to maneuver again in the same round." A
    `MANEUVER_HOOK` provider offering a strike-bundled maneuver (one whose
    own grant will call `commit_strike_for_round`) must gate its own offer on
    `not strike_committed_this_round(context)` -- the same "provider consults
    a shared flag at its own offer-time gate" convention
    `additional_strike_limit_used` already establishes for the "(limited)"
    additional-strike cap (module docstring's "Cross-card '(limited)' cap"
    section) -- *not* enforced centrally by `_ask_maneuver`/`hooks.offer`
    itself: the engine cannot tell, before a provider's own `apply()` runs,
    which of its offered `HookOption`s are strike-bundled versus plain, so it
    cannot filter them out of the offered list on a provider's behalf.
    `commit_strike_for_round` itself raises `ValueError` if called a second
    time for the same vampire the same round, as a loud backstop against a
    provider that forgets this gate (see its own docstring) -- but the gate
    below is still what a correctly-written provider must consult to avoid
    even *offering* an illegal second option in the first place (CLAUDE.md
    "decision points, not hard-coded play": an illegal choice must never
    reach a `Decision` at all).

    This is *not* a block on maneuvering in general: a combatant who has
    already committed a strike-bundled maneuver this round may still use a
    *plain*, non-strike-bundled maneuver afterward -- the quoted restriction
    only bars a *second strike card or weapon* source, not maneuvering as
    such. A plain `MANEUVER_HOOK` provider (Saku Pihlajamäki, Pursuit's basic
    "[cel] Maneuver." clause, Dance with the Devil, Fleetness) must never
    consult this.

    Degrades to `False` if `ROUND_STATE_CONTEXT_KEY` is missing from
    `context` (the hook offered directly, bypassing `run_combat`, as several
    scenario tests do to probe one provider in isolation) -- matching every
    other degrade-gracefully helper in this module."""
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if round_state is None:
        return False
    return context["vampire"] in round_state.get(COMMITTED_STRIKE_KEY, {})


def commit_strike_for_round(context: Mapping[str, Any], strike: hooks.HookOption) -> None:
    """Pre-commit `context["vampire"]`'s initial strike of the round to
    `strike` (see `COMMITTED_STRIKE_KEY`'s own docstring and the module
    docstring's "Maneuver bundled with a strike" section, OQ-28).

    Call this only from a `MANEUVER_HOOK` provider's own grant -- specifically
    from the same closure that applies the maneuver itself -- when, and only
    when, that provider's printed text bundles the maneuver together with
    choosing a strike (e.g. Slam's superior "[POT] As above, with 1 optional
    maneuver, only usable to get to close range," where "as above" is the
    same card's own "Strike: hand strike at +2 damage" clause; .44 Magnum's
    "Strike: 2R damage, with 1 optional maneuver each combat" is the
    identically-shaped weapon-side example). The provider must have already
    gated its own offer on `not strike_committed_this_round(context)` (see
    that function's own docstring) -- this function raises `ValueError` if a
    commitment is already recorded for this vampire this round, as a loud
    backstop against a provider that forgets that gate (Rulebook SS4 Combat
    > Determine Range: "they cannot use a second strike card or weapon to
    maneuver again in the same round" -- silently overwriting the first
    commitment instead of refusing it outright would let a second such
    maneuver illegally take effect with no error raised, exactly the
    mis-resolution CLAUDE.md's "never mis-resolves a card" milestone
    forbids).

    `strike` must be a `HookOption` whose `apply(state)` returns an `int` or
    `StrikeDamage`, exactly the contract a `COMBAT_STRIKE_OPTION_HOOK`
    provider's own `apply` already follows -- it is invoked later, at
    strike-resolution time (never here, at maneuver time), so it can read
    whatever live state (e.g. the current base hand-strike damage) is only
    settled by then. `strike.choice.value` must not collide with the two
    built-in strike choices (`HAND_STRIKE_VALUE`, `NO_STRIKE_VALUE`) -- name
    it like any other card-sourced choice value (e.g. `"slam:superior"`), the
    same convention every other hook option in this project already follows;
    this function raises `ValueError` on a collision rather than relying on
    convention alone (a collision would otherwise silently mis-resolve
    `_resolve_one_strike`'s own `if choice == ...` branching onto the wrong,
    built-in effect instead of the intended one).

    A plain maneuver *not* bundled with a strike (Saku Pihlajamäki's printed
    ability, Pursuit's basic "[cel] Maneuver." clause, Dance with the Devil,
    Fleetness) must never call this -- doing so would wrongly lock that
    combatant's strike choice with no textual basis; see `cards/pursuit.py`'s
    own module docstring (OQ-27) for the citation distinguishing the two
    shapes.

    A missing `ROUND_STATE_CONTEXT_KEY` entry in `context` (the hook offered
    directly, bypassing `run_combat` -- as several scenario tests do, to
    probe one provider in isolation) is a no-op, matching `mark_additional_
    strike_limit_used`'s own degrade-gracefully convention: there is nothing
    to persist to, and a test exercising this mechanism end-to-end must run
    it through `run_combat` (or construct and thread its own shared dict)."""
    if strike.choice.value in (HAND_STRIKE_VALUE, NO_STRIKE_VALUE):
        raise ValueError(
            f"commit_strike_for_round: strike.choice.value {strike.choice.value!r} collides "
            "with a built-in strike choice -- use a card-specific value instead"
        )
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if round_state is None:
        return
    committed = round_state.setdefault(COMMITTED_STRIKE_KEY, {})
    vampire_id = context["vampire"]
    if vampire_id in committed:
        raise ValueError(
            "commit_strike_for_round: vampire "
            f"{vampire_id!r} already has a committed strike this round -- Rulebook SS4 Combat "
            "> Determine Range: a minion cannot use a second strike card or weapon to maneuver "
            "again in the same round; the offering provider must gate itself on "
            "strike_committed_this_round(context) before returning this option"
        )
    committed[vampire_id] = strike


def _is_ready(vampire: VampireInPlay) -> bool:
    return vampire.zone == "ready"


def _strike_strength(
    state: GameState, player: str, vampire: VampireInPlay, opponent: VampireInPlay
) -> int:
    """Hand strike = base strength (default 1, Rulebook SS4 Combat) plus any
    passive `combat_strength_modifier` contribution (see module docstring)."""
    return HAND_STRIKE_STRENGTH + hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK,
        state,
        player=player,
        vampire=vampire.instance_id,
        opponent=opponent.instance_id,
    )


def _ask_strike(
    state: GameState,
    player: str,
    vampire: VampireInPlay,
    opponent: VampireInPlay,
    round_state: dict[str, Any],
) -> tuple[str, dict[str, hooks.HookOption], frozenset[str]]:
    """Offer every strike choice legal right now: the two built-ins, every
    registered `combat_strike_option` (a card-granted alternate strike that
    deals its own damage), and every registered `combat_dodge_option` (a
    card-granted dodge -- see module docstring; dodge is never a built-in
    choice, only ever card/ability-granted).

    `round_state` is the current round's shared "(limited)"-additional-
    strike scratch dict (module docstring's "Cross-card '(limited)' cap"
    section); threaded only into the `combat_dodge_option` offer, since a
    dodge-bundled grant is the only one of the two hooks this function calls
    that can originate a "(limited)" additional-strike grant
    (`combat_strike_option` grants a plain alternate strike, never an
    *additional* one).

    Returns `(chosen_value, options_by_value, dodge_values)`: `dodge_values`
    is the subset of `options_by_value`'s keys that came from
    `combat_dodge_option` rather than `combat_strike_option`, so the caller
    can apply dodge's damage-nullifying effect itself rather than trusting a
    provider's `apply` return value for it (see module docstring).

    Maneuver-committed strike (module docstring's "Maneuver bundled with a
    strike" section, OQ-28 `docs/OPEN_QUESTIONS.md`): if `commit_strike_for_
    round` recorded a pre-committed strike for this combatant earlier this
    round (Determine Range runs strictly before the strike step every round),
    that entry is popped from `round_state` and resolved directly here --
    *no* `Decision` is raised at all for this call, matching "the combatant
    does not get an independent, later choice at the strike step." Popping
    (not merely reading) the entry is what correctly limits this to the
    combatant's *initial* strike of the round only, per the rulebook's own
    wording -- a later Additional Strikes pair calling this function again
    for the same combatant finds nothing left and gets the engine's normal,
    fully independent strike choice.
    """
    # Relies on this being the first `_ask_strike` call for `vampire` since
    # Determine Range committed the entry (true today: Determine Range always
    # finishes before the strike step begins, and no other call site reads
    # COMMITTED_STRIKE_KEY) -- a future engine change interleaving another
    # strike-step-shaped call between Determine Range and here would need to
    # re-check this assumption.
    committed = round_state.get(COMMITTED_STRIKE_KEY, {}).pop(vampire.instance_id, None)
    if committed is not None:
        return committed.choice.value, {committed.choice.value: committed}, frozenset()
    strike_options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK,
        state,
        player=player,
        vampire=vampire.instance_id,
        opponent=opponent.instance_id,
    )
    dodge_options = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK,
        state,
        player=player,
        vampire=vampire.instance_id,
        opponent=opponent.instance_id,
        round_state=round_state,
    )
    by_value = {o.choice.value: o for o in strike_options}
    by_value.update({o.choice.value: o for o in dodge_options})
    dodge_values = frozenset(o.choice.value for o in dodge_options)
    choices = (
        (
            Choice(HAND_STRIKE_VALUE, "Hand strike"),
            Choice(NO_STRIKE_VALUE, "Do not strike this round"),
        )
        + tuple(o.choice for o in strike_options)
        + tuple(o.choice for o in dodge_options)
    )
    decision = Decision(
        player=player,
        kind="strike_choice",
        choices=choices,
        context={"vampire": vampire.instance_id},
    )
    return state.ask(decision).value, by_value, dodge_values


def _resolve_one_strike(
    state: GameState,
    player: str,
    vampire: VampireInPlay,
    opponent: VampireInPlay,
    round_state: dict[str, Any],
    *,
    participates: bool,
) -> tuple[int, bool, bool]:
    """Resolve one combatant's strike for one strike-pair step.

    `round_state` is forwarded unchanged to `_ask_strike` (see its own
    docstring and the module docstring's "Cross-card '(limited)' cap"
    section).

    `participates=False` means this combatant has no strike to make in this
    particular pair -- e.g. an additional-strike pair they did not opt into
    (Rulebook SS4 Combat > Additional Strikes: "another choose strike step
    and resolve strike step in which only the minions with additional
    strikes may play strike cards") -- so no choice is offered at all
    (CLAUDE.md "only when needed": no vacuous `Decision`).

    Returns `(damage_dealt, dodges, ignore_opponent_dodge)`.

    `dodges` is True iff this combatant chose a `combat_dodge_option`: their
    own strike always deals 0 damage (Strike Effects > Dodge: "A dodge
    strike deals no damage") -- enforced here directly rather than trusting
    the provider's `apply` return value -- and the caller must zero out
    whatever damage the *opponent's* simultaneous strike would otherwise
    deal to this combatant ("it protects the dodging minion ... from the
    effects of the opposing strike"), *unless* that opponent's strike is
    itself dodge-proof (see `ignore_opponent_dodge` below and the module
    docstring's "Dodge-proof strikes" section).

    `ignore_opponent_dodge` is True iff *this* combatant's own strike (not
    the dodge case -- a dodge never carries this) is flagged
    `StrikeDamage(..., ignore_dodge=True)` by its provider: the opponent's
    dodge, if they chose one, has no effect against this specific strike.
    """
    if not participates:
        return 0, False, False
    choice, by_value, dodge_values = _ask_strike(state, player, vampire, opponent, round_state)
    if choice in dodge_values:
        by_value[choice].apply(state)  # dodge's own side effect, if any
        return 0, True, False
    if choice == HAND_STRIKE_VALUE:
        return _strike_strength(state, player, vampire, opponent), False, False
    if choice == NO_STRIKE_VALUE:
        return 0, False, False
    result = by_value[choice].apply(state)  # card-granted strike option: its own damage
    if isinstance(result, StrikeDamage):
        return result.amount, False, result.ignore_dodge
    return result, False, False


def _resolve_strike_pair(
    state: GameState,
    acting_player: str,
    acting_vampire: VampireInPlay,
    blocking_player: str,
    blocking_vampire: VampireInPlay,
    round_state: dict[str, Any],
    *,
    acting_participates: bool = True,
    blocking_participates: bool = True,
) -> None:
    """One choose-strike/resolve-strike step (Rulebook SS4 Combat > Combat
    Sequence, step 4): acting minion's controller chooses first, then both
    strikes' damage is resolved simultaneously -- except a dodge zeroes the
    damage the *opponent's* strike would otherwise deal to the dodging
    combatant, unless that opponent's strike is itself dodge-proof (see
    `_resolve_one_strike` and the module docstring's "Dodge-proof strikes"
    section). Used both for the normal pair and for each additional-strike
    pair (`acting_participates`/`blocking_participates` = False for a
    combatant not striking in this particular pair).

    `round_state` is the current round's shared "(limited)"-additional-
    strike scratch dict, forwarded unchanged to both `_resolve_one_strike`
    calls (and, through them, to `_ask_strike`'s `combat_dodge_option`
    offer) -- the *same* object every time this function is called within
    one round, per `run_combat`'s own round-scoped lifetime for it (module
    docstring's "Cross-card '(limited)' cap" section).
    """
    damage_to_blocking, acting_dodges, acting_ignore_dodge = _resolve_one_strike(
        state,
        acting_player,
        acting_vampire,
        blocking_vampire,
        round_state,
        participates=acting_participates,
    )
    if state.game_over:
        return
    damage_to_acting, blocking_dodges, blocking_ignore_dodge = _resolve_one_strike(
        state,
        blocking_player,
        blocking_vampire,
        acting_vampire,
        round_state,
        participates=blocking_participates,
    )
    if acting_dodges and not blocking_ignore_dodge:
        damage_to_acting = 0
    if blocking_dodges and not acting_ignore_dodge:
        damage_to_blocking = 0

    # Simultaneous: both strikes' damage is resolved in the same step,
    # neither combatant's mend decision can react to the other's. `round_
    # state` is forwarded so `apply_damage` can record this round's "blood
    # lost to damage" total (module docstring's "End of Round and
    # round-scoped blood-loss tracking" section, OQ-29).
    # OQ-44: torpor-triggered pool losses (e.g. Fame) from both sides are one
    # event; ousting is decided once afterwards (both at 0 = tie). The second
    # side's damage is therefore still resolved (mend decision included),
    # deliberately: it can turn a single oust into a tie or save the other
    # side. Inside the window the `game_over` guards in damage.py do not
    # short-circuit, and `resolve_pending_ousts` re-filters pool <= 0, so a
    # pool gain by a doomed player in the window would cancel the queued oust.
    with simultaneous_pool_losses(state):
        if damage_to_blocking:
            apply_damage(
                state,
                blocking_player,
                blocking_vampire,
                normal=damage_to_blocking,
                round_state=round_state,
            )
        if damage_to_acting:
            apply_damage(
                state,
                acting_player,
                acting_vampire,
                normal=damage_to_acting,
                round_state=round_state,
            )


def _ask_additional_strike(
    state: GameState,
    player: str,
    vampire: VampireInPlay,
    opponent: VampireInPlay,
    round_state: dict[str, Any],
) -> bool:
    """Offer every currently-available `combat_additional_strike` grant
    (Rulebook SS4 Combat > Additional Strikes -- see module docstring). No
    options registered/currently available => no decision raised at all
    (CLAUDE.md "only when needed").

    `round_state` is the current round's shared "(limited)"-additional-
    strike scratch dict, threaded into the `combat_additional_strike`
    context (module docstring's "Cross-card '(limited)' cap" section) --
    this is the *direct*-grant hook (as opposed to `_ask_strike`'s
    dodge-bundled one), so a provider implementing a "(limited)" clause
    reads it to decide whether to offer its own grant at all, and a provider
    implementing an *exempt* clause simply never consults it.

    Returns whether this combatant uses one now. If so, the chosen option's
    `apply(state)` has already consumed the grant (e.g. decrementing a
    provider-owned counter) before returning -- the caller is responsible
    for then running a full, independent strike choice for this combatant
    (`_resolve_one_strike`/`_ask_strike`), exactly like a normal strike:
    an additional strike is never a fixed/hardcoded hand strike.
    """
    options = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK,
        state,
        player=player,
        vampire=vampire.instance_id,
        opponent=opponent.instance_id,
        round_state=round_state,
    )
    if not options:
        return False
    by_value = {o.choice.value: o for o in options}
    choices = tuple(o.choice for o in options) + (Choice(hooks.PASS_VALUE, "Do not use it"),)
    decision = Decision(
        player=player,
        kind="additional_strike_choice",
        choices=choices,
        context={"vampire": vampire.instance_id},
    )
    answer = state.ask(decision).value
    if answer == hooks.PASS_VALUE:
        return False
    by_value[answer].apply(state)
    return True


def _flip_range(range_: str) -> str:
    return LONG_RANGE if range_ == CLOSE_RANGE else CLOSE_RANGE


def _ask_maneuver(
    state: GameState,
    player: str,
    vampire: VampireInPlay,
    opponent: VampireInPlay,
    combat_state: dict[str, Any],
    round_state: dict[str, Any],
) -> bool:
    """Offer this combatant's controller every currently-available
    `MANEUVER_HOOK` grant for one turn of the Determine Range step (module
    docstring's "Determine Range and maneuvers" section) -- both a plain
    ability-granted maneuver *not* bundled with choosing a strike (e.g. Saku
    Pihlajamäki's printed "1 optional maneuver each combat", Pursuit's basic
    clause) and a maneuver genuinely "from a strike" (Slam, .44 Magnum -- see
    module docstring's "Maneuver bundled with a strike" section, OQ-28): both
    shapes register against this same hook, the distinction lives entirely in
    whether a given provider also calls `commit_strike_for_round`.

    `combat_state` is the shared, *combat*-scoped (not round-scoped --
    `COMBAT_STATE_CONTEXT_KEY`) scratch dict, threaded into the hook context
    so a provider like Saku's own can record its one-time, whole-combat use.

    `round_state` is the current round's shared scratch dict (module
    docstring's "Cross-card '(limited)' cap" and "Maneuver bundled with a
    strike" sections), threaded into the hook context under `round_state=`
    (`ROUND_STATE_CONTEXT_KEY`) so a strike-bundled maneuver's own grant can
    call `commit_strike_for_round` from its `apply`-time closure; a plain
    maneuver provider simply never reads it.

    No options registered/currently available => no `Decision` raised at all
    (CLAUDE.md "only when needed"). Returns whether this combatant plays a
    maneuver now; `_determine_range` flips the range if so.
    """
    options = hooks.offer(
        MANEUVER_HOOK,
        state,
        player=player,
        vampire=vampire.instance_id,
        opponent=opponent.instance_id,
        combat_state=combat_state,
        round_state=round_state,
    )
    if not options:
        return False
    by_value = {o.choice.value: o for o in options}
    choices = tuple(o.choice for o in options) + (Choice(hooks.PASS_VALUE, "Do not maneuver"),)
    decision = Decision(
        player=player,
        kind="maneuver_choice",
        choices=choices,
        context={"vampire": vampire.instance_id},
    )
    answer = state.ask(decision).value
    if answer == hooks.PASS_VALUE:
        return False
    by_value[answer].apply(state)
    return True


def _determine_range(
    state: GameState,
    acting_player: str,
    acting_vampire: VampireInPlay,
    blocking_player: str,
    blocking_vampire: VampireInPlay,
    combat_state: dict[str, Any],
    round_state: dict[str, Any],
) -> None:
    """Rulebook SS4 Combat > Combat Sequence step 2, "Determine Range" (see
    module docstring's verbatim quote and its "Turn order and termination"
    paragraph for the sourcing of the alternation/closing rule implemented
    here). Sets `state.combat_range` for this round.

    `round_state` is this round's shared scratch dict, forwarded unchanged to
    every `_ask_maneuver` call this step makes (module docstring's "Maneuver
    bundled with a strike" section, OQ-28) -- the *same* object `run_combat`
    goes on to use for the strike step immediately afterward, so a
    strike-bundled maneuver claimed here is visible to `_ask_strike` later
    this same round.
    """
    state.combat_range = CLOSE_RANGE  # "Close range is the default for each round."
    turns = (
        (acting_player, acting_vampire, blocking_vampire),
        (blocking_player, blocking_vampire, acting_vampire),
    )
    turn_index = 0
    consecutive_declines = 0
    while consecutive_declines < 2 and not state.game_over:
        player, vampire, opponent = turns[turn_index]
        if _ask_maneuver(state, player, vampire, opponent, combat_state, round_state):
            state.combat_range = _flip_range(state.combat_range)
            consecutive_declines = 0
        else:
            consecutive_declines += 1
        turn_index = 1 - turn_index


def _ask_press(state: GameState, player: str, vampire: VampireInPlay) -> str:
    choices = (
        Choice("press", "Press: continue combat to another round"),
        Choice("end_combat", "Do not press"),
    )
    decision = Decision(
        player=player, kind="press", choices=choices, context={"vampire": vampire.instance_id}
    )
    return state.ask(decision).value


def _ask_end_of_round(
    state: GameState,
    acting_player: str,
    acting_vampire: VampireInPlay,
    blocking_player: str,
    blocking_vampire: VampireInPlay,
    round_state: dict[str, Any],
) -> None:
    """Rulebook SS4 Combat > Combat Sequence, step 7, "End of Round: End of
    round cards and effects are played here" (module docstring's "End of
    Round and round-scoped blood-loss tracking" section, OQ-29 `docs/
    OPEN_QUESTIONS.md`). Dispatched as the engine's standard two-sided
    impulse window (CLAUDE.md rule 4 / Rulebook SS2 Sequencing, `hooks.
    resolve_impulse_window`) -- the same "acting Methuselah gets the impulse
    first ... window closes when both pass" shape every other two-sided
    card-option window in this project already uses (`engine/politics.py::
    _run_pre_cast_hook_window`, `engine/phases/minion.py::_perform_bleed`'s
    own `BLEED_AMOUNT_MODIFIER_HOOK`), rather than `_ask_press`'s own
    narrower "ask each side once, in order, first 'yes' wins" shape (Press is
    a single binary decision per side, not a window where either side may
    play an arbitrary number of card effects); only the *ordering*
    precedent -- acting combatant's controller offered first -- is shared
    with `_ask_press` (module docstring's own Press-step-order paragraph,
    OQ-3).

    Called exactly once per round by `run_combat`, on every path out of a
    round's own processing -- a normal end (nobody pressed), a premature end
    (a combatant went not-ready before the Press step was even reached), and
    the "someone pressed, another round follows" case alike (Taste of Vitae's
    own ruling: "Must be played after the presses are handled and can be
    played if the round ends prematurely" [RTR 20001020] [LSJ 20001024]
    [RTR 20030519] -- the window fires in the premature case too, even though
    no Press decision ever actually occurred).

    Context carries `acting_player`/`acting_vampire`/`blocking_player`/
    `blocking_vampire` (plain `str` ids, never the live object -- `Decision.
    context` reaches agent-visible code, CLAUDE.md "information hiding") so a
    provider can tell, from `context["player"]` alone, which side is its own
    controller and which vampire is "this vampire" versus "the opposing
    vampire"; and `round_state=` (`ROUND_STATE_CONTEXT_KEY`), the same
    shared, round-scoped scratch dict `_ask_maneuver`/`_ask_strike` already
    receive this round, so a provider can read this round's `engine/
    damage.py::blood_lost_to_damage_this_round` record before it is discarded
    at the top of the next round.
    """
    hooks.resolve_impulse_window(
        state,
        END_OF_ROUND_HOOK,
        acting_player,
        blocking_player,
        context={
            "acting_player": acting_player,
            "acting_vampire": acting_vampire.instance_id,
            "blocking_player": blocking_player,
            "blocking_vampire": blocking_vampire.instance_id,
            ROUND_STATE_CONTEXT_KEY: round_state,
        },
    )


def _ask_before_range(
    state: GameState,
    acting_player: str,
    acting_vampire: VampireInPlay,
    blocking_player: str,
    blocking_vampire: VampireInPlay,
) -> None:
    """Rulebook SS4 Combat > Combat Sequence, step 1, "Before Range: Play
    cards before range is chosen" (module docstring's "Before Range"
    section, OQ-47 `docs/OPEN_QUESTIONS.md`, resolved). Dispatched exactly
    once per combat by `run_combat`, immediately before round 1's own
    Determine Range step -- see that call site for the one-shot guard.

    Mirrors `_ask_end_of_round`'s own two-sided, repeatable impulse-window
    shape and ordering precedent (acting combatant's controller first,
    OQ-3) -- see this function's own module-docstring section for why a
    binary `_ask_press`-style ask does not fit here instead.
    """
    hooks.resolve_impulse_window(
        state,
        BEFORE_RANGE_HOOK,
        acting_player,
        blocking_player,
        context={
            "acting_player": acting_player,
            "acting_vampire": acting_vampire.instance_id,
            "blocking_player": blocking_player,
            "blocking_vampire": blocking_vampire.instance_id,
        },
    )


def run_combat(
    state: GameState,
    acting_player: str,
    acting_vampire: VampireInPlay,
    blocking_player: str,
    blocking_vampire: VampireInPlay,
    initial_combat_state: dict[str, Any] | None = None,
) -> None:
    """Resolve combat between the acting and the (successfully) blocking minion.

    `initial_combat_state` (OQ-25, `docs/OPEN_QUESTIONS.md`, resolved -- module
    docstring's "Pre-combat grant seeding" section): if given, used *directly*
    (not copied) as this combat's `combat_state` instead of starting from a
    fresh `{}` -- lets a caller pre-seed a grant that must already exist
    before this combat's very first round (e.g.
    `seed_pre_combat_maneuver_grant`). `None` (every call site before this
    pass, and every call site with nothing to pre-seed) reproduces the
    previous, always-`{}`-at-the-top behaviour exactly.
    """
    # One combat-scoped scratch dict, created once for the whole combat (not
    # recreated per round, unlike round_state below) -- module docstring's
    # "Determine Range and maneuvers" section, "Per-combat, not per-round,
    # scoping" paragraph.
    combat_state: dict[str, Any] = initial_combat_state if initial_combat_state is not None else {}
    before_range_offered = False
    while True:
        if state.game_over:
            break  # Rulebook SS5: play continues only while 2+ Methuselahs remain.
        if not (_is_ready(acting_vampire) and _is_ready(blocking_vampire)):
            break  # Rulebook SS4: combat ends at once if a combatant is no longer ready.

        # --- Before Range step (Rulebook SS4 Combat > Combat Sequence step
        # 1; module docstring's "Before Range" section, OQ-47): offered
        # exactly once per combat, before round 1's own Determine Range step
        # -- never again on a later round of the same combat. ---
        if not before_range_offered:
            _ask_before_range(
                state, acting_player, acting_vampire, blocking_player, blocking_vampire
            )
            before_range_offered = True
            if state.game_over:
                break

        # One fresh, shared round-scoped scratch dict per round (module
        # docstring's "Cross-card '(limited)' cap" and "Maneuver bundled with
        # a strike" sections): created here, at the top of every iteration of
        # this loop, so it never carries a flag over into a later round of
        # the *same* combat, and threaded unchanged into every hook offer
        # below for this round only -- including Determine Range's own
        # MANEUVER_HOOK offers, so a strike-bundled maneuver claimed there is
        # visible to the strike step immediately afterward (OQ-28).
        round_state: dict[str, Any] = {}

        # --- Determine Range step (Rulebook SS4 Combat > Combat Sequence
        # step 2; see module docstring): resolved before the strike step
        # every round, same ordering as the rulebook's own numbered list. ---
        _determine_range(
            state,
            acting_player,
            acting_vampire,
            blocking_player,
            blocking_vampire,
            combat_state,
            round_state,
        )
        if state.game_over:
            break

        # --- Strike step: acting minion's controller chooses first; simultaneous resolution. ---
        _resolve_strike_pair(
            state, acting_player, acting_vampire, blocking_player, blocking_vampire, round_state
        )
        if state.game_over:
            break

        # `still_ready` tracks whether this round's processing continues past
        # each "combat ends at once if a combatant is no longer ready" check
        # (Rulebook SS4) -- rather than `break`ing out of `run_combat`'s own
        # loop immediately at each such point as before, so that the single
        # `_ask_end_of_round` call below (module docstring's "End of Round and
        # round-scoped blood-loss tracking" section, OQ-29) is still reached
        # on every path out of the round, including a premature one.
        still_ready = _is_ready(acting_vampire) and _is_ready(blocking_vampire)

        # --- Additional strikes (Rulebook SS4 Combat > Additional Strikes;
        # see module docstring): resolved after the normal pair, as repeated
        # choose-strike/resolve-strike steps -- acting combatant decides
        # whether to use an available grant first, each time -- "repeated as
        # necessary" while either combatant still has an unused grant. Skipped
        # entirely once `still_ready` is already False, same as the previous
        # immediate `break` would have skipped it. ---
        if still_ready:
            while not state.game_over:
                acting_extra = _ask_additional_strike(
                    state, acting_player, acting_vampire, blocking_vampire, round_state
                )
                blocking_extra = _ask_additional_strike(
                    state, blocking_player, blocking_vampire, acting_vampire, round_state
                )
                if not acting_extra and not blocking_extra:
                    break
                _resolve_strike_pair(
                    state,
                    acting_player,
                    acting_vampire,
                    blocking_player,
                    blocking_vampire,
                    round_state,
                    acting_participates=acting_extra,
                    blocking_participates=blocking_extra,
                )
                if state.game_over or not (
                    _is_ready(acting_vampire) and _is_ready(blocking_vampire)
                ):
                    break
            still_ready = _is_ready(acting_vampire) and _is_ready(blocking_vampire)

        # --- Press step: the acting minion's controller always goes first
        # (Rulebook SS2 Sequencing; see module docstring / OQ-3). Skipped
        # entirely if the round already ended prematurely (`still_ready` is
        # False) -- same as the previous immediate `break` would have. ---
        pressed = False
        if still_ready and not state.game_over:
            order = [(acting_player, acting_vampire), (blocking_player, blocking_vampire)]
            for player, vampire in order:
                if _ask_press(state, player, vampire) == "press":
                    pressed = True
                    break

        # --- End of Round step (Rulebook SS4 Combat > Combat Sequence, step
        # 7; module docstring's "End of Round and round-scoped blood-loss
        # tracking" section, OQ-29): fires exactly once per round, on every
        # path out of it -- a normal end, a premature end, or "someone
        # pressed, another round follows" -- positioned here, after where the
        # Press step sits above, whether or not Press actually ran this
        # round. ---
        _ask_end_of_round(
            state, acting_player, acting_vampire, blocking_player, blocking_vampire, round_state
        )

        if state.game_over or not still_ready or not pressed:
            break
    state.combat_range = None  # no combat in progress once run_combat returns
