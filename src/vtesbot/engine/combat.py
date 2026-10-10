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

Combat-card hook wiring (`engine/hooks.py`, CLAUDE.md milestone-3 scaffolding
pass): the strike step offers each combatant's controller every registered
`"combat_strike_option"` alongside the two built-in choices (a card-granted
strike option's `apply(state)` must return the damage it inflicts, so it can
fully stand in for a hand strike -- e.g. a card that adds flat damage to a
hand strike); `"combat_strength_modifier"` is a passive, mandatory numeric
hook (CLAUDE.md rule 3 exception) summed into the base hand-strike strength,
for printed vampire abilities that are not a choice (e.g. a flat "+1
strength" line or a clan-conditional combat bonus). With no providers
registered for either hook, every strike is exactly a plain hand strike at
strength 1 -- byte-for-byte the milestone-2 result. Maneuvers and ranged
strikes remain out of scope this pass (no combat card in the current pool's
classification needs them *without* also needing the maneuver/range
mechanic itself, which is a separate, larger future engine change -- see the
rules-engineer milestone-3 scaffolding report).

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

  Cross-card, per-minion "(limited)" cap (resolves `docs/OPEN_QUESTIONS.md`
  OQ-19, closing a gap `cards/dust_up.py`/`cards/side_strike.py` previously
  flagged as "a candidate for a future `rules-engineer` pass": both tracked
  their own clause's "(limited)" use in a private, per-vampire-*instance*,
  effectively-forever dict, since no round-boundary signal existed anywhere
  in this module for a hook provider to see). The SS8 rule quoted above is a
  *cross-card*, round-scoped cap ("a minion cannot use more than one card or
  effect ... per round of combat") -- cross-*card* (not per-card), but still
  strictly per-*minion*: the Wauneka/Flávio Gonçalves worked example two
  paragraphs above is itself two different minions each legally using their
  own additional-strike grant in the *same* round, so the cap must never be
  pooled jointly across both combatants, only within each one's own. `run_
  combat` now creates one fresh, shared `round_state: dict[str, Any]` at the
  top of every round (reset every round, never carried into the next) and
  threads it, under the context key `ROUND_STATE_CONTEXT_KEY`, into both
  `COMBAT_DODGE_OPTION_HOOK`'s and `COMBAT_ADDITIONAL_STRIKE_HOOK`'s own hook
  context -- the two, and only two, hooks where a "(limited)" additional-
  strike grant can originate (`COMBAT_STRIKE_OPTION_HOOK`'s plain alternate-
  strike grants never grant an *additional* strike, so they need no access
  to this cap). `additional_strike_limit_used`/`mark_additional_strike_
  limit_used` (below) read/write a flag *keyed by vampire instance id*
  inside that shared dict (never a single flat boolean, since `round_state`
  is the same object offered to both combatants each round -- a flat
  boolean would wrongly let one combatant's own play block the *other*,
  unrelated combatant's own grant); a card module implementing a "(limited)"
  additional-strike clause (e.g. Dust Up's `[cel]`, Side Strike's `[CEL]`)
  must consult/record it from its own grant -- this is what actually
  enforces the cap *across* different cards (or a second physical copy of
  the same card) held by the *same* vampire in the same round, closing a
  real illegal-play gap the previous per-card-only tracking left open
  (nothing previously stopped a vampire holding both Dust Up and Side Strike
  from using *both* cards' grants in one round), while still correctly
  leaving each combatant's own cap independent of the other's. Per Dust
  Up's own ruling on exactly where the check belongs ("[cel] The additional
  strike is not optional: you cannot play it for the dodge only if you
  already played it for a (limited) additional strike this round" [ANK
  20220204]), the check gates the *granting* clause itself (a dodge-bundled
  grant counts identically to a direct one) -- not the later act of
  claiming an already-recorded grant, which needs no re-check (nothing in
  the rules revokes a legitimately granted strike mid-round). A card
  implementing an *exempt* clause per its own printed text (e.g. a future
  Quickness `[CEL]`/Hell-for-Leather `[cel]` "additional strike that does
  not count against the limit") simply never calls either helper for that
  clause -- the cap remains, as before, the granting card's own choice to
  consult, not something this generic mechanism imposes unconditionally;
  see `additional_strike_limit_used`'s own docstring for a warning about
  this convention-only (not enforced) exemption boundary.

With no providers registered for either hook, no dodge/additional-strike
choice is ever offered and the additional-strike loop exits immediately --
byte-for-byte the previous (pre-Gap-2) result.

Dodge-proof strikes (`rules-auditor` finding on the first Gap 2 pass): the
Golden Rule for Cards (CLAUDE.md SS2 / Rulebook SS3 "whenever the cards
contradict the rules, the cards take precedence") lets a specific strike's
own printed text override the normal dodge rule for that strike only --
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

Known future gap (deliberately not built -- no card in the current pool's
classification needs it, milestone-2 scope is hand-strikes-only): dodge as
implemented here only nullifies numeric *damage*. Strike Effects > Dodge
protects from "the effects of the opposing strike" more broadly (e.g. a
future Steal Blood-style strike's non-damage effect); `_resolve_one_strike`
currently has no mechanism to suppress a non-damage `apply(state)` side
effect for a dodging combatant. A future combat card needing this will need
to extend `COMBAT_STRIKE_OPTION_HOOK`'s contract again.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import hooks
from .damage import apply_damage
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

HAND_STRIKE_STRENGTH = 1
COMBAT_STRIKE_OPTION_HOOK = "combat_strike_option"
COMBAT_STRENGTH_MODIFIER_HOOK = "combat_strength_modifier"
COMBAT_DODGE_OPTION_HOOK = "combat_dodge_option"
COMBAT_ADDITIONAL_STRIKE_HOOK = "combat_additional_strike"

ROUND_STATE_CONTEXT_KEY = "round_state"
"""Context key, under `COMBAT_DODGE_OPTION_HOOK`/`COMBAT_ADDITIONAL_STRIKE_
HOOK`, for the shared, round-scoped scratch `dict[str, Any]` `run_combat`
creates fresh at the top of every round (see module docstring's "Cross-card
'(limited)' cap" section). A hook offered directly, bypassing `run_combat`
(as several scenario tests do, to probe one hook in isolation), simply has
no entry under this key; `additional_strike_limit_used`/`mark_additional_
strike_limit_used` below both treat that as "no shared state available" and
degrade gracefully (see their own docstrings) rather than raising."""

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
    """
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
            Choice("hand_strike", "Hand strike"),
            Choice("no_strike", "Do not strike this round"),
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
    if choice == "hand_strike":
        return _strike_strength(state, player, vampire, opponent), False, False
    if choice == "no_strike":
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
    # neither combatant's mend decision can react to the other's.
    if damage_to_blocking:
        apply_damage(state, blocking_player, blocking_vampire, normal=damage_to_blocking)
    if damage_to_acting:
        apply_damage(state, acting_player, acting_vampire, normal=damage_to_acting)


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


def _ask_press(state: GameState, player: str, vampire: VampireInPlay) -> str:
    choices = (
        Choice("press", "Press: continue combat to another round"),
        Choice("end_combat", "Do not press"),
    )
    decision = Decision(
        player=player, kind="press", choices=choices, context={"vampire": vampire.instance_id}
    )
    return state.ask(decision).value


def run_combat(
    state: GameState,
    acting_player: str,
    acting_vampire: VampireInPlay,
    blocking_player: str,
    blocking_vampire: VampireInPlay,
) -> None:
    """Resolve combat between the acting and the (successfully) blocking minion."""
    while True:
        if not (_is_ready(acting_vampire) and _is_ready(blocking_vampire)):
            break  # Rulebook SS4: combat ends at once if a combatant is no longer ready.

        # One fresh, shared "(limited)"-additional-strike scratch dict per
        # round (module docstring's "Cross-card '(limited)' cap" section):
        # created here, at the top of every iteration of this loop, so it
        # never carries a flag over into a later round of the *same* combat,
        # and threaded unchanged into every hook offer below for this round
        # only.
        round_state: dict[str, Any] = {}

        # --- Strike step: acting minion's controller chooses first; simultaneous resolution. ---
        _resolve_strike_pair(
            state, acting_player, acting_vampire, blocking_player, blocking_vampire, round_state
        )

        if not (_is_ready(acting_vampire) and _is_ready(blocking_vampire)):
            break

        # --- Additional strikes (Rulebook SS4 Combat > Additional Strikes;
        # see module docstring): resolved after the normal pair, as repeated
        # choose-strike/resolve-strike steps -- acting combatant decides
        # whether to use an available grant first, each time -- "repeated as
        # necessary" while either combatant still has an unused grant. ---
        while True:
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
            if not (_is_ready(acting_vampire) and _is_ready(blocking_vampire)):
                break
        if not (_is_ready(acting_vampire) and _is_ready(blocking_vampire)):
            break

        # --- Press step: the acting minion's controller always goes first
        # (Rulebook SS2 Sequencing; see module docstring / OQ-3). ---
        order = [(acting_player, acting_vampire), (blocking_player, blocking_vampire)]

        pressed = False
        for player, vampire in order:
            if _ask_press(state, player, vampire) == "press":
                pressed = True
                break
        if not pressed:
            break
