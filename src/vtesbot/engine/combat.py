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
  the second with only Flávio striking). The "(limited)"/"one card or effect
  per round" cap itself is the *granting* card's own business (e.g. Dust
  Up's own future module would need to track that it only grants once per
  round), not this generic mechanism's -- the hook simply stops being
  offered once a provider's own grant is exhausted.

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

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
    state: GameState, player: str, vampire: VampireInPlay, opponent: VampireInPlay
) -> tuple[str, dict[str, hooks.HookOption], frozenset[str]]:
    """Offer every strike choice legal right now: the two built-ins, every
    registered `combat_strike_option` (a card-granted alternate strike that
    deals its own damage), and every registered `combat_dodge_option` (a
    card-granted dodge -- see module docstring; dodge is never a built-in
    choice, only ever card/ability-granted).

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
    *,
    participates: bool,
) -> tuple[int, bool, bool]:
    """Resolve one combatant's strike for one strike-pair step.

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
    choice, by_value, dodge_values = _ask_strike(state, player, vampire, opponent)
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
    """
    damage_to_blocking, acting_dodges, acting_ignore_dodge = _resolve_one_strike(
        state, acting_player, acting_vampire, blocking_vampire, participates=acting_participates
    )
    damage_to_acting, blocking_dodges, blocking_ignore_dodge = _resolve_one_strike(
        state, blocking_player, blocking_vampire, acting_vampire, participates=blocking_participates
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
    state: GameState, player: str, vampire: VampireInPlay, opponent: VampireInPlay
) -> bool:
    """Offer every currently-available `combat_additional_strike` grant
    (Rulebook SS4 Combat > Additional Strikes -- see module docstring). No
    options registered/currently available => no decision raised at all
    (CLAUDE.md "only when needed").

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

        # --- Strike step: acting minion's controller chooses first; simultaneous resolution. ---
        _resolve_strike_pair(
            state, acting_player, acting_vampire, blocking_player, blocking_vampire
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
                state, acting_player, acting_vampire, blocking_vampire
            )
            blocking_extra = _ask_additional_strike(
                state, blocking_player, blocking_vampire, acting_vampire
            )
            if not acting_extra and not blocking_extra:
                break
            _resolve_strike_pair(
                state,
                acting_player,
                acting_vampire,
                blocking_player,
                blocking_vampire,
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
