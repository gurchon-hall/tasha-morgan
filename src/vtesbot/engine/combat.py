"""Basic combat: hand strikes, maneuvers/range, dodge, additional strikes,
before-range and end-of-round windows (Rulebook §4 Combat). See
RUL-002, ENG-012, ENG-013, ENG-017, RUL-008, ENG-019, ENG-020, ENG-029, ENG-040."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import hooks
from .damage import (
    COMBAT_STATE_CONTEXT_KEY,
    ROUND_NUMBER_KEY,
    ROUND_STATE_CONTEXT_KEY,
    apply_damage,
)
from .decision import Choice, Decision
from .pool import simultaneous_pool_losses

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

HAND_STRIKE_STRENGTH = 1
HAND_STRIKE_VALUE = "hand_strike"
NO_STRIKE_VALUE = "no_strike"
"""The two built-in strike choices `_ask_strike` always offers (Rulebook
§4). Named constants so `commit_strike_for_round` can reject a colliding
card-sourced value."""
COMBAT_STRIKE_OPTION_HOOK = "combat_strike_option"
COMBAT_STRENGTH_MODIFIER_HOOK = "combat_strength_modifier"
COMBAT_DODGE_OPTION_HOOK = "combat_dodge_option"
COMBAT_ADDITIONAL_STRIKE_HOOK = "combat_additional_strike"
MANEUVER_HOOK = "maneuver"
"""Matches `Hook.MANEUVER`'s string value."""
END_OF_ROUND_HOOK = "end_of_round"
"""Matches `Hook.END_OF_ROUND`'s string value (ENG-020)."""
BEFORE_RANGE_HOOK = "before_range"
"""Matches `Hook.BEFORE_RANGE`'s string value (ENG-029)."""

CLOSE_RANGE = "close"
LONG_RANGE = "long"
"""The two legal values of `GameState.combat_range` (Rulebook §4 Determine
Range)."""

# COMBAT_STATE_CONTEXT_KEY is imported from .damage above (canonical
# definition lives there, to avoid a circular import -- see that module's
# own docstring); re-exported under this name for every card module that
# already imports it from here (`seed_pre_combat_maneuver_grant`'s own
# siblings below, `cards/saku_pihlajamaki.py`, `tests/rules/test_pre_combat_
# maneuver_grant.py`). Besides `MANEUVER_HOOK`/`DAMAGE_PREVENTION_HOOK`, also
# threaded into `BEFORE_RANGE_HOOK`'s context (`_ask_before_range`),
# `COMBAT_STRENGTH_MODIFIER_HOOK`'s context (`hand_strike_strength`/
# `_strike_strength`, reached via `_resolve_one_strike`/`_resolve_strike_
# pair`), and `COMBAT_STRIKE_OPTION_HOOK`'s context (`_ask_strike`, so a
# card-sourced strike-substitute provider's own `hand_strike_strength` call
# sees the same bonus a plain hand strike does -- rules-auditor finding,
# see that function's own docstring) -- lets a provider activated before
# range is determined record a flag/bonus in `combat_state` that a later
# strike's own strength computation, in any round of the *same* combat,
# reads back (e.g. Kasim Bayar, krcg 201598). A fresh `run_combat` call
# creates a new `combat_state` dict, so nothing here ever leaks into a
# separate, later combat for the same vampire in the same turn.

PRE_COMBAT_MANEUVER_GRANT_KEY = "pre_combat_maneuver_grants"
"""Key inside `combat_state` for a pre-combat maneuver grant seeded via
`run_combat`'s `initial_combat_state` (ENG-017); `dict[str, int]` keyed by
vampire id."""


def seed_pre_combat_maneuver_grant(vampire_id: str, count: int = 1) -> dict[str, Any]:
    """Build an `initial_combat_state` seed (ENG-017) granting `vampire_id`
    `count` unclaimed pre-combat maneuvers, for `run_combat`/
    `perform_minion_action`."""
    return {PRE_COMBAT_MANEUVER_GRANT_KEY: {vampire_id: count}}


def pre_combat_maneuver_available(context: Mapping[str, Any]) -> bool:
    """Whether `context["vampire"]` has an unclaimed pre-combat maneuver
    grant (ENG-017); missing `combat_state` degrades to False."""
    combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
    if combat_state is None:
        return False
    return combat_state.get(PRE_COMBAT_MANEUVER_GRANT_KEY, {}).get(context["vampire"], 0) > 0


def consume_pre_combat_maneuver_grant(context: Mapping[str, Any]) -> None:
    """Consume one of `context["vampire"]`'s unclaimed pre-combat maneuver
    grants (ENG-017); missing state or none left is a no-op."""
    combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
    if combat_state is None:
        return
    grants = combat_state.get(PRE_COMBAT_MANEUVER_GRANT_KEY, {})
    vampire_id = context["vampire"]
    if grants.get(vampire_id, 0) > 0:
        grants[vampire_id] -= 1


BLOCK_TIME_COMBAT_GRANT_KEY = "block_time_combat_grants"
"""Key inside `combat_state` (ENG-040): `dict[str, dict[str, int]]`, vampire
instance id -> {grant_name: count}, for a one-shot combat-time effect grant
earned by a reaction played during the block attempt's own stealth/
intercept resolution (before `run_combat` is even called), seeded via
`run_combat`'s `initial_combat_state` by `action.py::perform_minion_
action` -- see `action.py::grant_block_time_combat_effect` for the
`pending`-side half of this mechanism, and that function's own docstring
for why this is forwarded only for the vampire that ends up the successful
blocker, never for any other candidate, and never into a second/follow-up
combat. Same per-vampire-dict shape as `PRE_COMBAT_MANEUVER_GRANT_KEY`,
generalized from a single named "maneuver" grant to arbitrary named
grants, since `DAMAGE_PREVENTION_HOOK` and other block-attempt-time
reactions are not maneuvers."""


def seed_block_time_combat_grants(grants: dict[str, dict[str, int]]) -> dict[str, Any]:
    """Build an `initial_combat_state` seed (ENG-040) from `action.py::
    perform_minion_action`'s own forwarded `pending[PENDING_BLOCK_TIME_
    COMBAT_GRANT_KEY]` bookkeeping. Used by `perform_minion_action` only;
    merges alongside any `seed_pre_combat_maneuver_grant` seed for the same
    combat (distinct top-level keys, never colliding)."""
    return {BLOCK_TIME_COMBAT_GRANT_KEY: grants}


def block_time_combat_grant_available(context: Mapping[str, Any], grant_name: str) -> bool:
    """Whether `context["vampire"]` currently has an unclaimed block-time
    combat grant named `grant_name` (ENG-040); missing `combat_state`
    degrades to False, same convention as `pre_combat_maneuver_available`."""
    combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
    if combat_state is None:
        return False
    per_vampire = combat_state.get(BLOCK_TIME_COMBAT_GRANT_KEY, {}).get(context["vampire"], {})
    return per_vampire.get(grant_name, 0) > 0


def consume_block_time_combat_grant(context: Mapping[str, Any], grant_name: str) -> None:
    """Consume one of `context["vampire"]`'s unclaimed block-time combat
    grants named `grant_name` (ENG-040); missing state or none left is a
    no-op, same convention as `consume_pre_combat_maneuver_grant`."""
    combat_state = context.get(COMBAT_STATE_CONTEXT_KEY)
    if combat_state is None:
        return
    per_vampire = combat_state.get(BLOCK_TIME_COMBAT_GRANT_KEY, {}).get(context["vampire"])
    if per_vampire and per_vampire.get(grant_name, 0) > 0:
        per_vampire[grant_name] -= 1


ADDITIONAL_STRIKE_LIMIT_KEY = "additional_strike_limit_used"
"""Key inside `round_state` for the "(limited)" additional-strike flag
(§8 glossary), a `dict[str, bool]` keyed per vampire id -- not a single
shared boolean."""


def additional_strike_limit_used(context: Mapping[str, Any]) -> bool:
    """Whether `context["vampire"]` already used a non-exempt "(limited)"
    additional-strike grant this round; an exempt clause must never call
    this. Missing `round_state` degrades to False."""
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if round_state is None:
        return False
    return bool(round_state.get(ADDITIONAL_STRIKE_LIMIT_KEY, {}).get(context["vampire"]))


def mark_additional_strike_limit_used(context: Mapping[str, Any]) -> None:
    """Record that `context["vampire"]` used a non-exempt "(limited)" grant
    this round; see `additional_strike_limit_used`. Missing `round_state`
    is a no-op."""
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if round_state is not None:
        round_state.setdefault(ADDITIONAL_STRIKE_LIMIT_KEY, {})[context["vampire"]] = True


@dataclass(frozen=True)
class StrikeDamage:
    """Richer return shape for a `COMBAT_STRIKE_OPTION_HOOK` provider's
    `apply`, flagging a strike dodge-proof. `amount` is the damage;
    `ignore_dodge=True` means the opponent's dodge has no effect."""

    amount: int
    ignore_dodge: bool = False


COMMITTED_STRIKE_KEY = "committed_strike"
"""Key inside `round_state` for a strike-bundled `MANEUVER_HOOK` grant
(ENG-019); popped by `_ask_strike`, also read as this round's "already
committed" flag."""


def strike_committed_this_round(context: Mapping[str, Any]) -> bool:
    """Whether `context["vampire"]` has a strike-bundled-maneuver
    commitment this round (ENG-019). A strike-bundled provider must gate its
    offer on this; a plain maneuver must never consult it."""
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if round_state is None:
        return False
    return context["vampire"] in round_state.get(COMMITTED_STRIKE_KEY, {})


def commit_strike_for_round(context: Mapping[str, Any], strike: hooks.HookOption) -> None:
    """Pre-commit `context["vampire"]`'s strike to `strike` (ENG-019), from a
    strike-bundled `MANEUVER_HOOK` grant only. Raises on a second
    commitment or a choice-value collision with a built-in."""
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
            f"{vampire_id!r} already has a committed strike this round -- Rulebook §4 Combat "
            "> Determine Range: a minion cannot use a second strike card or weapon to maneuver "
            "again in the same round; the offering provider must gate itself on "
            "strike_committed_this_round(context) before returning this option"
        )
    committed[vampire_id] = strike


def _is_ready(vampire: VampireInPlay) -> bool:
    return vampire.zone == "ready"


def hand_strike_strength(
    state: GameState,
    player: str,
    vampire: str,
    opponent: str,
    combat_state: Mapping[str, Any] | None = None,
) -> int:
    """The damage a plain hand strike deals right now (Rulebook §4): base
    strength (`HAND_STRIKE_STRENGTH`) plus any live `COMBAT_STRENGTH_
    MODIFIER_HOOK` contribution. `combat_state` (ENG-040, same combat-scoped
    scratch dict `MANEUVER_HOOK`/`DAMAGE_PREVENTION_HOOK` already receive)
    is threaded into the hook's context so a provider can read back a
    whole-combat-duration bonus activated earlier in the same combat (e.g.
    a `BEFORE_RANGE_HOOK` option granting "+N strength that combat").

    Takes instance ids, not `VampireInPlay` objects, since that is the
    shape every card module already has on hand from its own hook
    `context` -- the single shared implementation every call site computing
    "what a plain hand strike would deal right now" to add a card-printed
    bonus on top of (`_strike_strength` below, plus `cards/dust_up.py`,
    `cards/slam.py`, `cards/weighted_walking_stick.py`) must go through,
    rather than each re-deriving the sum independently: that previously let
    `combat_state` reach `_strike_strength` without reaching the three card
    modules' own copies, so a `COMBAT_STRENGTH_MODIFIER_HOOK` provider
    reading `combat_state` (e.g. the prospective Kasim Bayar, krcg 201598)
    would have silently contributed 0 whenever the bonused vampire struck
    via one of those cards instead of a plain hand strike (rules-auditor
    finding). `combat_state` defaults to `None` for a call site that
    genuinely has none to forward (e.g. a hook offered directly in a test,
    bypassing `run_combat`); every production call site should still pass
    its own context's value through."""
    return HAND_STRIKE_STRENGTH + hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK,
        state,
        player=player,
        vampire=vampire,
        opponent=opponent,
        combat_state=combat_state,
    )


def _strike_strength(
    state: GameState,
    player: str,
    vampire: VampireInPlay,
    opponent: VampireInPlay,
    combat_state: dict[str, Any],
) -> int:
    """Thin adapter over `hand_strike_strength` for this module's own call
    sites, which hold `VampireInPlay` objects rather than instance ids."""
    return hand_strike_strength(
        state, player, vampire.instance_id, opponent.instance_id, combat_state
    )


def _ask_strike(
    state: GameState,
    player: str,
    vampire: VampireInPlay,
    opponent: VampireInPlay,
    round_state: dict[str, Any],
    combat_state: dict[str, Any],
) -> tuple[str, dict[str, hooks.HookOption], frozenset[str]]:
    """Offer every legal strike: the two built-ins, `combat_strike_option`,
    `combat_dodge_option`. Pops a maneuver-committed strike first (ENG-019).
    Returns `(chosen_value, options_by_value, dodge_values)`. `combat_state`
    (ENG-040) is threaded into `COMBAT_STRIKE_OPTION_HOOK`'s own context --
    not just into `_strike_strength`'s separate call below -- so a card-sourced
    strike-substitute provider computing its own "+N damage over a plain
    hand strike" (e.g. `cards/dust_up.py`, `cards/slam.py`, `cards/
    weighted_walking_stick.py`, via `hand_strike_strength`) can read back the
    same whole-combat-duration bonus a plain hand strike sees."""
    # Relies on this being the first _ask_strike call for vampire since
    # Determine Range always finishes before the strike step begins.
    committed = round_state.get(COMMITTED_STRIKE_KEY, {}).pop(vampire.instance_id, None)
    if committed is not None:
        return committed.choice.value, {committed.choice.value: committed}, frozenset()
    strike_options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK,
        state,
        player=player,
        vampire=vampire.instance_id,
        opponent=opponent.instance_id,
        combat_state=combat_state,
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
    combat_state: dict[str, Any],
    *,
    participates: bool,
) -> tuple[int, bool, bool]:
    """Resolve one combatant's strike for one strike-pair step (ENG-012/ENG-019).
    `participates=False` offers no choice. Returns `(damage, dodges,
    ignore_opponent_dodge)`; dodge zeroes damage unless dodge-proof."""
    if not participates:
        return 0, False, False
    choice, by_value, dodge_values = _ask_strike(
        state, player, vampire, opponent, round_state, combat_state
    )
    if choice in dodge_values:
        by_value[choice].apply(state)  # dodge's own side effect, if any
        return 0, True, False
    if choice == HAND_STRIKE_VALUE:
        return _strike_strength(state, player, vampire, opponent, combat_state), False, False
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
    combat_state: dict[str, Any],
    round_state: dict[str, Any],
    *,
    acting_participates: bool = True,
    blocking_participates: bool = True,
) -> None:
    """One choose/resolve-strike step (Rulebook §4 step 4): acting minion
    chooses first, strikes resolve simultaneously. Used for the normal and
    each additional-strike pair."""
    damage_to_blocking, acting_dodges, acting_ignore_dodge = _resolve_one_strike(
        state,
        acting_player,
        acting_vampire,
        blocking_vampire,
        round_state,
        combat_state,
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
        combat_state,
        participates=blocking_participates,
    )
    if acting_dodges and not blocking_ignore_dodge:
        damage_to_acting = 0
    if blocking_dodges and not acting_ignore_dodge:
        damage_to_blocking = 0

    # Simultaneous: both strikes resolve in one step (round_state records
    # blood lost, ENG-020).

    # DES-010: both sides' damage still resolves deliberately (simultaneous
    # torpor pool losses are one event, oust decided only afterwards).
    with simultaneous_pool_losses(state):
        if damage_to_blocking:
            apply_damage(
                state,
                blocking_player,
                blocking_vampire,
                normal=damage_to_blocking,
                round_state=round_state,
                inflicted_by=acting_vampire.instance_id,
                combat_state=combat_state,
            )
        if damage_to_acting:
            apply_damage(
                state,
                acting_player,
                acting_vampire,
                normal=damage_to_acting,
                round_state=round_state,
                inflicted_by=blocking_vampire.instance_id,
                combat_state=combat_state,
            )


def _ask_additional_strike(
    state: GameState,
    player: str,
    vampire: VampireInPlay,
    opponent: VampireInPlay,
    round_state: dict[str, Any],
) -> bool:
    """Offer every available `combat_additional_strike` grant (Rulebook §4).
    No options => no `Decision`. Returns whether a grant is used now."""
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
    """Offer every available `MANEUVER_HOOK` grant for one Determine Range
    turn (ENG-017/RUL-008/ENG-019); plain and strike-bundled maneuvers share this hook.
    Returns whether one was played."""
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
    """Rulebook §4 Determine Range step: alternates `_ask_maneuver` turns,
    closing on two consecutive declines, enforcing "no two in a row" by
    loop shape. Sets `state.combat_range`."""
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
    """Offer one combatant's controller a single press/decline choice
    (Rulebook §4 step 6). Returns `"press"`/`"end_combat"`; see
    `_resolve_press` for how repeated asks combine."""
    choices = (
        Choice("press", "Press: continue combat to another round"),
        Choice("end_combat", "Do not press"),
    )
    decision = Decision(
        player=player, kind="press", choices=choices, context={"vampire": vampire.instance_id}
    )
    return state.ask(decision).value


def _resolve_press(
    state: GameState,
    acting_player: str,
    acting_vampire: VampireInPlay,
    blocking_player: str,
    blocking_vampire: VampireInPlay,
) -> bool:
    """Rulebook §4 step 6 (Press): alternates acting-first (RUL-002),
    like `_determine_range`. A press toggles (not sets), making
    two-in-a-row structurally impossible. Returns whether a press
    remains."""
    turns = (
        (acting_player, acting_vampire),
        (blocking_player, blocking_vampire),
    )
    turn_index = 0
    consecutive_declines = 0
    pressed = False
    while consecutive_declines < 2 and not state.game_over:
        player, vampire = turns[turn_index]
        if _ask_press(state, player, vampire) == "press":
            pressed = not pressed
            consecutive_declines = 0
        else:
            consecutive_declines += 1
        turn_index = 1 - turn_index
    return pressed


def _ask_end_of_round(
    state: GameState,
    acting_player: str,
    acting_vampire: VampireInPlay,
    blocking_player: str,
    blocking_vampire: VampireInPlay,
    round_state: dict[str, Any],
) -> None:
    """Rulebook §4 step 7, End of Round (ENG-020): two-sided impulse window,
    acting combatant first (RUL-002). Called exactly once per round on every
    exit path, even a premature one."""
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
    combat_state: dict[str, Any],
) -> None:
    """Rulebook §4 step 1, Before Range (ENG-029): two-sided impulse window,
    acting combatant first (RUL-002). Dispatched exactly once per combat,
    before round 1's Determine Range. `combat_state` (ENG-040) is threaded
    into the hook's context -- same combat-scoped scratch dict `MANEUVER_
    HOOK`/`DAMAGE_PREVENTION_HOOK` already receive -- so a provider acting
    here can record a once-per-combat flag and/or a whole-combat-duration
    effect `COMBAT_STRENGTH_MODIFIER_HOOK` reads back on every later strike
    of this same combat (e.g. Kasim Bayar, krcg 201598: discard a political
    action here for "+2 strength that combat")."""
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
            COMBAT_STATE_CONTEXT_KEY: combat_state,
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
    """Resolve combat between the acting and blocking minion (Rulebook §4
    Combat). `initial_combat_state` (ENG-017/ENG-040) pre-seeds a grant that must
    exist before round 1 -- a pre-combat maneuver grant
    (`seed_pre_combat_maneuver_grant`), a block-attempt-time combat grant
    (`seed_block_time_combat_grants`), or both (distinct top-level keys,
    merged by the caller)."""
    # One combat-scoped scratch dict, created once for the whole combat
    # (not recreated per round, unlike round_state below).
    combat_state: dict[str, Any] = initial_combat_state if initial_combat_state is not None else {}
    before_range_offered = False
    round_number = 0
    while True:
        if state.game_over:
            break  # Rulebook §5: play continues only while 2+ Methuselahs remain.
        if not (_is_ready(acting_vampire) and _is_ready(blocking_vampire)):
            break  # Rulebook §4: combat ends at once if a combatant is no longer ready.

        # --- Before Range step (Rulebook §4 step 1, ENG-029): offered once
        # per combat, before round 1's Determine Range step. ---
        if not before_range_offered:
            _ask_before_range(
                state,
                acting_player,
                acting_vampire,
                blocking_player,
                blocking_vampire,
                combat_state,
            )
            before_range_offered = True
            if state.game_over:
                break

        round_number += 1
        # One fresh round-scoped scratch dict per round (ENG-012/ENG-019); never
        # carries a flag into a later round of the same combat. Pre-seeded
        # with this round's 1-indexed number (ENG-040) so a
        # `DAMAGE_PREVENTION_HOOK` provider can tell "is this round 1"
        # (`damage.py::is_round_one`) without needing `combat_state`'s own
        # cross-round persistence for that part.
        round_state: dict[str, Any] = {ROUND_NUMBER_KEY: round_number}

        # --- Determine Range step (Rulebook §4 step 2): before strikes. ---
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

        # still_ready tracks the "combat ends at once if no longer ready"
        # check (Rulebook §4) without an early break, so _ask_end_of_round
        # (ENG-020) below is still reached on every path, even a premature one.
        still_ready = _is_ready(acting_vampire) and _is_ready(blocking_vampire)

        # --- Additional strikes (Rulebook §4): repeated choose/resolve
        # pairs while either combatant has an unused grant. Skipped if
        # still_ready is already False. ---
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
                    combat_state,
                    round_state,
                    acting_participates=acting_extra,
                    blocking_participates=blocking_extra,
                )
                if state.game_over or not (
                    _is_ready(acting_vampire) and _is_ready(blocking_vampire)
                ):
                    break
            still_ready = _is_ready(acting_vampire) and _is_ready(blocking_vampire)

        # --- Press step (Rulebook §4 step 6): alternating press/decline
        # turns, acting minion's controller first (RUL-002). Skipped if the
        # round already ended prematurely. ---
        pressed = False
        if still_ready and not state.game_over:
            pressed = _resolve_press(
                state, acting_player, acting_vampire, blocking_player, blocking_vampire
            )

        # --- End of Round step (Rulebook §4 step 7, ENG-020): fires exactly
        # once per round, on every exit path. ---
        _ask_end_of_round(
            state, acting_player, acting_vampire, blocking_player, blocking_vampire, round_state
        )

        if state.game_over or not still_ready or not pressed:
            break
    state.combat_range = None  # no combat in progress once run_combat returns
