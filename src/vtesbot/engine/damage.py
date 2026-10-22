"""Damage resolution: prevent, mend (normal only), wounded->torpor->burn (§4). Aggravated
wounds+torpors a healthy vampire in one step. ENG-020: round-scoped blood-lost tracking for
Taste of Vitae. ENG-036: `DAMAGE_PREVENTION_HOOK`'s own context also carries `round_state`
(`ROUND_STATE_CONTEXT_KEY`), for a once-per-round prevention cap (e.g. Soak), and
`apply_damage` also supports a mandatory, round-scoped "prevent all further damage" effect
(`MANDATORY_FULL_PREVENTION_KEY`/`mandatory_full_prevention_active`/
`mark_mandatory_full_prevention_active`), for a once-activated-then-automatic effect (e.g.
Rolling with the Punches' superior clause) -- distinct from `DAMAGE_PREVENTION_HOOK` itself,
which only ever offers a freely-declinable choice. ENG-040: `round_state` now also carries a
1-indexed `ROUND_NUMBER_KEY`, written by `combat.py::run_combat` at the top of each round
(`is_round_one` query helper), and `DAMAGE_PREVENTION_HOOK`'s own context also carries the
combat-scoped `combat_state` (`COMBAT_STATE_CONTEXT_KEY`, canonical home here -- `combat.py`
imports it, not the reverse, same reasoning as `ROUND_STATE_CONTEXT_KEY`'s own docstring) --
together let a provider gate a "round 1 of the resulting combat only, if this vampire
blocked" effect (e.g. Precognition, krcg 101475) via `combat.py::block_time_combat_grant_
available`/`consume_block_time_combat_grant`."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from . import hooks
from .attachments import effective_capacity
from .decision import Choice, Decision
from .hooks import Hook

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

DAMAGE_PREVENTION_HOOK = Hook.DAMAGE_PREVENTION

COMBAT_STATE_CONTEXT_KEY = "combat_state"
"""Context key for the shared, combat-scoped (not round-scoped) scratch dict
`combat.py::run_combat` creates once per combat (ENG-040; canonical definition
lives here, not `engine/combat.py`, for the same circular-import reason as
`ROUND_STATE_CONTEXT_KEY` below -- `combat.py` imports `apply_damage` from
this module). `combat.py::COMBAT_STATE_CONTEXT_KEY` re-exports this same
object. Threaded into `MANEUVER_HOOK`'s own context (already, e.g. Saku
Pihlajamäki's once-per-combat grant), `DAMAGE_PREVENTION_HOOK`'s own
context (ENG-040 addition, below), and -- as of the same combat-state-plumbing
pass -- `BEFORE_RANGE_HOOK`'s and `COMBAT_STRENGTH_MODIFIER_HOOK`'s own
contexts (`combat.py::_ask_before_range`/`hand_strike_damage`) so a provider
can read/write combat-scoped state (e.g. `combat.py`'s block-time combat
grant helpers, or a once-per-combat strength bonus activated before range is
determined and read back on every later strike of the same combat) from any
of these hooks."""

ROUND_NUMBER_KEY = "round_number"
"""Key in the round-scoped scratch dict (ENG-040): the 1-indexed round number
for the current round, written once by `combat.py::run_combat` at the top of
each round's own loop iteration -- lets a `DAMAGE_PREVENTION_HOOK` provider
gate a "round 1 only" effect (e.g. Precognition, krcg 101475, "this vampire
can prevent 1 damage during the first round of the resulting combat") without
needing `combat_state`'s own cross-round persistence for that part. See
`is_round_one` below."""


def is_round_one(round_state: Mapping[str, Any] | None) -> bool:
    """Whether the current round is round 1 of its combat (ENG-040 query
    helper). `round_state is None` (a hook offered outside `run_combat`, or
    before this key existed) degrades to False, same convention as every
    other round-scoped query in this module."""
    if round_state is None:
        return False
    return round_state.get(ROUND_NUMBER_KEY) == 1


ROUND_STATE_CONTEXT_KEY = "round_state"
"""Context key for the shared, round-scoped scratch dict `combat.run_combat`
creates fresh each round (ENG-012/ENG-019); canonical definition lives here (not
`engine/combat.py`, which imports `apply_damage` from this module -- defining
it there too would be circular) so a `DAMAGE_PREVENTION_HOOK` provider can
read/write round-scoped state (ENG-036) the same way combat-scoped hooks
already do. `engine/combat.py::ROUND_STATE_CONTEXT_KEY` re-exports this same
object; degrades to no entry when a hook is offered directly."""
VAMPIRE_ENTERS_TORPOR_HOOK = Hook.VAMPIRE_ENTERS_TORPOR
"""Mandatory reaction hook, dispatched by `send_to_torpor` (ENG-014, Fame). Passes the live
`VampireInPlay`, safe since `run_effects` only runs trusted card code."""


BLOOD_LOST_TO_DAMAGE_KEY = "blood_lost_to_damage"
"""Key in the round-scoped scratch dict (ENG-020): per vampire id, blood lost this round
to `apply_damage`'s Mend/aggravated-burn steps only. `dict[str, int]`."""


def record_blood_lost_to_damage(
    round_state: dict[str, Any] | None, vampire_id: str, amount: int
) -> None:
    """Add `amount` to `vampire_id`'s running total this round (`BLOOD_LOST_TO_DAMAGE_KEY`).
    `round_state is None` or non-positive `amount` is a no-op."""
    if round_state is None or amount <= 0:
        return
    totals = round_state.setdefault(BLOOD_LOST_TO_DAMAGE_KEY, {})
    totals[vampire_id] = totals.get(vampire_id, 0) + amount


def blood_lost_to_damage_this_round(round_state: Mapping[str, Any] | None, vampire_id: str) -> int:
    """Blood `vampire_id` lost to damage this round (ENG-020 query helper, e.g. Taste of
    Vitae). `round_state` is caller-supplied to avoid a circular import; `None` -> 0."""
    if round_state is None:
        return 0
    return round_state.get(BLOOD_LOST_TO_DAMAGE_KEY, {}).get(vampire_id, 0)


DAMAGE_SUCCESSFULLY_INFLICTED_KEY = "damage_successfully_inflicted"
"""Key in the round-scoped scratch dict: per *inflicting* vampire id, the post-prevention,
pre-mend normal+aggravated total it landed this round -- "damage successfully inflicted" is
the rulebook's own combat-resolution term (step 4, damage resolution, before the mend
sub-step), confirmed card-rulings-side by "Counts up damage successfully inflicted during
the round ... retainers and environmental damage do not count." [TOM 19950304]
[LSJ 20010812]. Deliberately distinct from `BLOOD_LOST_TO_DAMAGE_KEY`, which is keyed by the
*damaged* vampire and only ever totals blood actually spent to mend/burn -- a vampire with 1
blood taking 3 normal damage loses only 1 blood to mending, but still "successfully
inflicted"/received 3. Needed by Pulled Fangs (krcg 101515)'s own playability trigger
("during a round during which this minion successfully inflicted more damage than the
opposing vampire"). `dict[str, int]`, same per-vampire-id-dict shape as
`BLOOD_LOST_TO_DAMAGE_KEY`."""


def record_damage_successfully_inflicted(
    round_state: dict[str, Any] | None, inflicted_by: str | None, amount: int
) -> None:
    """Add `amount` to `inflicted_by`'s running total this round
    (`DAMAGE_SUCCESSFULLY_INFLICTED_KEY`). `round_state is None`, `inflicted_by is None`
    (damage with no attributable attacker, e.g. a retainer/environmental source -- see this
    key's own docstring), or non-positive `amount` is a no-op -- mirrors
    `record_blood_lost_to_damage`'s own degrade-to-no-op contract."""
    if round_state is None or inflicted_by is None or amount <= 0:
        return
    totals = round_state.setdefault(DAMAGE_SUCCESSFULLY_INFLICTED_KEY, {})
    totals[inflicted_by] = totals.get(inflicted_by, 0) + amount


def damage_successfully_inflicted_this_round(
    round_state: Mapping[str, Any] | None, vampire_id: str
) -> int:
    """Damage `vampire_id` successfully inflicted (as the attacker) this round -- the query
    side of `DAMAGE_SUCCESSFULLY_INFLICTED_KEY`, e.g. Pulled Fangs comparing the two
    combatants' own totals at end of round. `round_state` is caller-supplied to avoid a
    circular import; `None` -> 0."""
    if round_state is None:
        return 0
    return round_state.get(DAMAGE_SUCCESSFULLY_INFLICTED_KEY, {}).get(vampire_id, 0)


MANDATORY_FULL_PREVENTION_KEY = "mandatory_full_prevention"
"""Key in the round-scoped scratch dict (ENG-036): per vampire id, whether a mandatory,
automatic "prevent all damage (normal and aggravated) this round" effect is active for the
rest of the round -- not a fresh offered choice. `dict[str, bool]`, same per-vampire-id-dict
shape as `combat.py`'s `ADDITIONAL_STRIKE_LIMIT_KEY`. Motivating case: Rolling with the
Punches' superior clause ("[FOR] Burn 1 blood to prevent all damage from the opposing
minion's strikes this round."), which `DAMAGE_PREVENTION_HOOK` alone cannot express -- that
hook only ever offers a freely-declinable choice (`hooks.offer_until_pass`), with no
primitive for "once chosen, applies unconditionally to every later occurrence this round"."""


def mandatory_full_prevention_active(
    round_state: Mapping[str, Any] | None, vampire_id: str
) -> bool:
    """Whether `vampire_id` has an active mandatory full-prevention effect this round
    (ENG-036; see `MANDATORY_FULL_PREVENTION_KEY`). `round_state is None` degrades to False,
    same convention as every other round-scoped cap in this codebase
    (`combat.py::additional_strike_limit_used`)."""
    if round_state is None:
        return False
    return bool(round_state.get(MANDATORY_FULL_PREVENTION_KEY, {}).get(vampire_id))


def mark_mandatory_full_prevention_active(
    round_state: dict[str, Any] | None, vampire_id: str
) -> None:
    """Activate a mandatory full-prevention effect for `vampire_id` for the remainder of the
    round (ENG-036; see `MANDATORY_FULL_PREVENTION_KEY`). Call once, from the activating
    option's own `apply` (e.g. Rolling with the Punches' superior clause) -- every later
    `apply_damage` call this round against the same vampire then zeroes its damage
    automatically, with no further decision offered. `round_state is None` is a no-op, same
    convention as `combat.py::mark_additional_strike_limit_used`."""
    if round_state is None:
        return
    round_state.setdefault(MANDATORY_FULL_PREVENTION_KEY, {})[vampire_id] = True


def add_blood(state: GameState, vampire: VampireInPlay, amount: int) -> int:
    """Add blood to a vampire, capped at its effective capacity (§1, ENG-002). Returns the
    amount actually added."""
    if amount <= 0:
        return 0
    added = min(amount, effective_capacity(state, vampire) - vampire.blood)
    vampire.blood += added
    return added


def burn_vampire(state: GameState, player: str, vampire: VampireInPlay) -> None:
    vampire.zone = "burned"
    vampire.locked = False
    state.log.record_event(f"{vampire.card.name} ({vampire.instance_id}) is burned")


def remove_vampire_from_game(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Remove a crypt card from the game (ENG-016; Wider View, 102180). Distinct zone from
    `burn_vampire` (see `VampireInPlay`). Guards against removing a contested vampire,
    unreachable today (ENG-016 addendum)."""
    if vampire.contested_with is not None:
        raise ValueError(
            "remove_vampire_from_game: removing a contested vampire is unhandled -- "
            "see this function's own docstring"
        )
    vampire.zone = "removed_from_game"
    vampire.locked = False


def send_to_torpor(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Torpor: controlled but not ready (§4 Torpor). Dispatches
    `VAMPIRE_ENTERS_TORPOR_HOOK` after the zone transition (ENG-014, Fame)."""
    vampire.zone = "torpor"
    vampire.locked = False
    state.log.record_event(f"{vampire.card.name} ({vampire.instance_id}) enters torpor")
    hooks.run_effects(VAMPIRE_ENTERS_TORPOR_HOOK, state, vampire=vampire, player=player)


def apply_damage(
    state: GameState,
    player: str,
    vampire: VampireInPlay,
    normal: int = 0,
    aggravated: int = 0,
    round_state: dict[str, Any] | None = None,
    inflicted_by: str | None = None,
    combat_state: dict[str, Any] | None = None,
) -> None:
    """Resolve `normal` + `aggravated` damage (§4). Order: prevent, mend (normal only),
    normal before aggravated. `round_state` (ENG-020) records blood spent when given;
    `None` is a no-op. A vampire with an active `MANDATORY_FULL_PREVENTION_KEY` effect
    (ENG-036) has all damage zeroed unconditionally before `DAMAGE_PREVENTION_HOOK` is even
    dispatched. `inflicted_by` (the attacking vampire's own instance id, when known) records
    the post-prevention total under `DAMAGE_SUCCESSFULLY_INFLICTED_KEY`, distinct from and
    in addition to `round_state`'s existing `BLOOD_LOST_TO_DAMAGE_KEY` bookkeeping -- see
    that key's own docstring. `combat_state` (ENG-040), when given by `combat.py::run_combat`'s
    own strike-resolution call sites, is threaded into `DAMAGE_PREVENTION_HOOK`'s context
    alongside `round_state`, so a provider can also consult combat-scoped state (e.g. a
    block-attempt-time grant, `combat.py::block_time_combat_grant_available`) together with
    `is_round_one(round_state)`; `None` (every call site outside `run_combat`, e.g. Pulled
    Fangs' own attachment-damage trigger) degrades to "no combat-scoped state available"."""
    if normal < 0 or aggravated < 0:
        raise ValueError("damage amounts must be non-negative")
    if normal == 0 and aggravated == 0:
        return
    state.log.record_event(
        f"{vampire.card.name} ({vampire.instance_id}) takes {normal} normal + "
        f"{aggravated} aggravated damage"
    )

    # --- Prevent step: single-sided window for the damaged vampire's own
    # controller (see module docstring); a "damage_box" is threaded through
    # so a registered prevention provider's `apply` can reduce it in place. ---
    damage_box = {"normal": normal, "aggravated": aggravated}
    if mandatory_full_prevention_active(round_state, vampire.instance_id):
        # ENG-036: a mandatory, already-activated effect (e.g. Rolling with the
        # Punches' superior clause) -- unconditional, no decision offered.
        # `DAMAGE_PREVENTION_HOOK` still dispatches below on the now-zeroed
        # box; every existing provider already gates on "nothing to prevent"
        # and offers nothing, so no special-case skip is needed.
        damage_box["normal"] = 0
        damage_box["aggravated"] = 0
    hooks.offer_until_pass(
        state,
        DAMAGE_PREVENTION_HOOK,
        player,
        context={
            "vampire": vampire.instance_id,
            "damage": damage_box,
            ROUND_STATE_CONTEXT_KEY: round_state,
            COMBAT_STATE_CONTEXT_KEY: combat_state,
        },
    )
    normal = max(0, damage_box["normal"])
    aggravated = max(0, damage_box["aggravated"])
    record_damage_successfully_inflicted(round_state, inflicted_by, normal + aggravated)
    if state.game_over or (normal == 0 and aggravated == 0):
        return

    # --- Mend step (normal damage only; aggravated cannot be mended). ---
    remaining_normal = normal
    if remaining_normal > 0 and vampire.blood > 0:
        max_mend = min(vampire.blood, remaining_normal)
        if max_mend > 0:
            choices = tuple(
                Choice(str(n), f"Mend {n} damage with blood") for n in range(max_mend + 1)
            )
            decision = Decision(
                player=player,
                kind="mend_damage",
                choices=choices,
                context={
                    "vampire": vampire.instance_id,
                    "damage": remaining_normal,
                    "blood": vampire.blood,
                },
            )
            mended = int(state.ask(decision).value)
            vampire.blood -= mended
            remaining_normal -= mended
            record_blood_lost_to_damage(round_state, vampire.instance_id, mended)

    # --- Resolve remaining normal damage (unmended -> wounded -> torpor). ---
    if remaining_normal > 0:
        if vampire.wounded:
            send_to_torpor(state, player, vampire)
        else:
            vampire.wounded = True

    # --- Aggravated damage: never mendable. Normal is handled first (above). ---
    for _ in range(aggravated):
        if state.game_over or vampire.zone == "burned":
            break
        if vampire.wounded:
            # "each point burns 1 blood or the vampire is burned" -- a forced
            # effect with no legal alternative (CLAUDE.md rule 3 exception
            # for mandatory effects defined by the rules): no decision offered.
            if vampire.blood > 0:
                vampire.blood -= 1
                record_blood_lost_to_damage(round_state, vampire.instance_id, 1)
            else:
                burn_vampire(state, player, vampire)
        else:
            # First aggravated point against a healthy vampire: wounds AND
            # sends straight to torpor (Nassir/Tamoszius worked examples;
            # unlike normal damage, there is no "merely wounded" state for
            # a healthy vampire taking aggravated damage).
            vampire.wounded = True
            send_to_torpor(state, player, vampire)
