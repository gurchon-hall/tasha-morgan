"""Damage resolution: prevent, then mend; wounded/torpor/burn progression.

Source: Rulebook SS4 Combat > Damage Resolution (per the `vtes-rules-reference`
skill condensed mapping): "1 blood mends 1 damage; unmended -> wounded ->
torpor. Aggravated cannot be mended; on a wounded vampire each point burns 1
blood or the vampire is burned. Normal damage is handled before aggravated."
This module implements the generic damage state machine so it can be driven
both by combat (`engine/combat.py`) and directly by future card effects /
scenario tests (mirroring the `rules-scenario-test` skill's own worked
example: `game.apply_damage(target=..., normal=..., aggravated=..., source=None)`).

Aggravated damage against a *healthy* (not yet wounded) vampire differs from
normal damage: it wounds AND sends the vampire straight to torpor in the
same step, rather than merely wounding (confirmed against the primary
rulebook's own worked examples, quoted by `rules-auditor` from
https://www.vekn.net/rulebook): Nassir (ready, 1 blood, takes 1 aggravated)
"cannot mend this damage, so he is wounded and goes to torpor with 1
blood"; Tamoszius (ready, 2 blood, takes 3 aggravated) is "wounded by 1,
burns 2 blood, [and] ends in torpor with no blood" -- i.e. the first
aggravated point wounds-and-torpors, and the remaining points (now applied
to an already-wounded, in-torpor vampire) each burn 1 blood or burn the
vampire, exactly as `apply_damage`'s existing wounded-vampire branch already
modelled. Ryan (already wounded, takes aggravated damage) is unaffected by
this fix and is covered by `test_aggravated_damage_burns_an_already_wounded_vampire`.

Vampire blood capacity cap (a vampire may never hold more blood than its
printed capacity) is a foundational, uncontested VTES rule (Rulebook SS1
Vampires) and is enforced here via `add_blood`.

Damage-prevention hook wiring (`engine/hooks.py`, CLAUDE.md milestone-3
scaffolding pass): the "Prevent step" named above is a single-sided window
(only the damaged vampire's controller may play a prevention effect, e.g.
Rolling with the Punches / Soak), so it is wired with
`hooks.offer_until_pass` against the `"damage_prevention"` hook. With no
providers registered (no prevention cards implemented yet) the offer is
always empty and no decision is raised -- byte-for-byte the milestone-2
result.

Round-scoped "blood lost to damage" tracking (OQ-29, `docs/
OPEN_QUESTIONS.md`, mechanism 2 -- Taste of Vitae, krcg id 101945, "This
vampire gains blood equal to the amount of blood lost by the opposing
vampire to damage this round"): `apply_damage` now accepts an optional
`round_state: dict[str, Any] | None = None` parameter. `engine/combat.py::
_resolve_strike_pair` (the only call site inside a combat round) passes the
current round's shared scratch dict (`engine/combat.py::
ROUND_STATE_CONTEXT_KEY`'s own object); every other existing call site
(direct card effects, scenario tests) passes nothing (`None`) and sees
byte-for-byte the previous, untracked behaviour. When given, exactly the
amount `vampire.blood` decreases from this function's own Mend step and its
own aggravated-burn step -- and only those two branches, since nothing else
in this function decreases blood -- is recorded via `record_blood_lost_to_
damage` into `BLOOD_LOST_TO_DAMAGE_KEY`, keyed by vampire instance id (so
the one shared `round_state` dict correctly keeps both combatants' own,
independent totals this round). `blood_lost_to_damage_this_round` is the
public helper a future card module queries (analogous to `engine/
combat.py::additional_strike_limit_used`/`commit_strike_for_round`'s own
public-helper shape); it lives here, not in `engine/combat.py`, and takes the
raw `round_state` dict directly rather than a hook `context` mapping, to
avoid a circular import (`engine/combat.py` already imports `apply_damage`
from this module) -- a provider reads `context.get(ROUND_STATE_CONTEXT_KEY)`
itself (the same pattern `cards/dust_up.py`'s own `_round_state` helper
already uses for its own, narrower state) and passes the result in. The
record is a plain dict entry keyed by instance id, untouched by any zone
transition (including `burn_vampire`), so it remains fully readable after
the tracked vampire is burned -- directly supporting Taste of Vitae's own
ruling "Can be played if the opponent was burned" [LSJ 20031201-2].
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from . import hooks
from .attachments import effective_capacity
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

DAMAGE_PREVENTION_HOOK = "damage_prevention"
VAMPIRE_ENTERS_TORPOR_HOOK = "vampire_enters_torpor"
"""Mandatory, non-chosen per-provider reaction hook (`hooks.run_effects`,
CLAUDE.md rule 3's "mandatory effects" exception -- nothing for a player to
choose, so no `Decision` is raised), dispatched by `send_to_torpor` itself,
the single call site every vampire's zone flips to `"torpor"` through.
Added resolving `docs/OPEN_QUESTIONS.md` OQ-22's own remaining clause for
Fame (100698, krcg id, "After this vampire goes to torpor, their controller
burns 3 pool"); `vampire` is passed as the live `VampireInPlay` object, not
merely its `instance_id` -- safe here (unlike a hook that raises a
`Decision`, which would reach `Observation`/agent-visible code, CLAUDE.md
"information hiding") because a `run_effects` provider only ever runs
trusted engine-adjacent card-module code, the same precedent
`engine/politics.py::_dispatch_referendum_tallied` already set for
`REFERENDUM_TALLIED_HOOK`'s own `caller_vampire` context entry."""


BLOOD_LOST_TO_DAMAGE_KEY = "blood_lost_to_damage"
"""Key inside a round-scoped scratch dict (`engine/combat.py::
ROUND_STATE_CONTEXT_KEY`'s own shared dict, when `apply_damage` is given
one as its own `round_state` argument) recording, per vampire instance id,
how much of that vampire's `blood` decreased this round specifically from
`apply_damage`'s own Mend step and aggravated-burn step -- not from any
other blood-moving effect (module docstring's "Round-scoped 'blood lost to
damage' tracking" section, OQ-29 `docs/OPEN_QUESTIONS.md`). Value is a
`dict[str, int]` keyed by vampire instance id, so the one shared dict
safely records both combatants' own, independent totals within the same
round (mirrors every other per-vampire-id-keyed sub-dict `engine/
combat.py`'s own `round_state` already carries, e.g.
`ADDITIONAL_STRIKE_LIMIT_KEY`)."""


def record_blood_lost_to_damage(
    round_state: dict[str, Any] | None, vampire_id: str, amount: int
) -> None:
    """Add `amount` to `vampire_id`'s running "blood lost to damage" total
    this round (see `BLOOD_LOST_TO_DAMAGE_KEY`). `round_state is None` (the
    common case -- most `apply_damage` callers, e.g. direct card effects or
    scenario tests, have no round in progress to record against) or a
    non-positive `amount` is a no-op, matching every other
    degrade-gracefully helper in this project (e.g. `engine/combat.py::
    mark_additional_strike_limit_used`)."""
    if round_state is None or amount <= 0:
        return
    totals = round_state.setdefault(BLOOD_LOST_TO_DAMAGE_KEY, {})
    totals[vampire_id] = totals.get(vampire_id, 0) + amount


def blood_lost_to_damage_this_round(round_state: Mapping[str, Any] | None, vampire_id: str) -> int:
    """How much of `vampire_id`'s blood has been lost to damage so far this
    round, attributable only to `apply_damage`'s own Mend/aggravated-burn
    branches (see `BLOOD_LOST_TO_DAMAGE_KEY`) -- the public helper a future
    card module (e.g. Taste of Vitae, OQ-29) queries, analogous to `engine/
    combat.py::additional_strike_limit_used`/`commit_strike_for_round`'s own
    public-helper shape. `round_state` is whatever a hook provider's own
    context carries under `engine/combat.py::ROUND_STATE_CONTEXT_KEY` (e.g.
    `context.get("round_state")`, the same pattern `cards/dust_up.py`'s own
    `_round_state` helper already uses) -- a card module reads that key
    itself and passes the result here, since this module has no dependency
    on `engine/combat.py`'s own context-key naming convention (avoiding a
    circular import: `engine/combat.py` already imports `apply_damage` from
    this module). `None` (no round in progress, or the hook was offered
    directly, bypassing `run_combat`) degrades to 0, matching the project's
    usual degrade-gracefully convention for round-scoped helpers."""
    if round_state is None:
        return 0
    return round_state.get(BLOOD_LOST_TO_DAMAGE_KEY, {}).get(vampire_id, 0)


def add_blood(state: GameState, vampire: VampireInPlay, amount: int) -> int:
    """Add blood to a vampire, capped at its effective capacity (Rulebook
    SS1 Vampires, printed capacity as modified by any attachment -- OQ-8,
    `docs/OPEN_QUESTIONS.md`; see `engine/attachments.py::effective_capacity`).

    Returns the amount actually added.
    """
    if amount <= 0:
        return 0
    added = min(amount, effective_capacity(state, vampire) - vampire.blood)
    vampire.blood += added
    return added


def burn_vampire(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Move a vampire out of play to the ash heap (destroyed)."""
    vampire.zone = "burned"
    vampire.locked = False


def remove_vampire_from_game(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Remove a crypt card from the game entirely (OQ-24, `docs/
    OPEN_QUESTIONS.md`; e.g. Wider View, krcg id 102180: "...remove a crypt
    card in your uncontrolled region from the game").

    Deliberately a distinct zone/function from `burn_vampire` -- see
    `VampireInPlay`'s own docstring for why `"removed_from_game"` is kept
    separate from `"burned"` rather than reusing it, even though both leave
    the vampire permanently out of play with `locked = False`.

    `rules-auditor` finding (OQ-24 addendum, `docs/OPEN_QUESTIONS.md`):
    nothing today can set `contested_with` on a still-`"uncontrolled"`
    vampire (`engine/contests.py::detect_contest_on_reveal` -- the only
    writer of `contested_with` -- only ever runs on a vampire *already*
    being revealed to `"ready"`), the only zone this function is ever
    called from, so a contested vampire being removed from the game is
    genuinely unreachable today. The guard below turns that
    currently-true-by-construction invariant into an enforced one, rather
    than leaving it implicit, so a future change that makes it reachable
    fails loudly instead of silently leaving a dangling `contested_with`
    reference on the vampire this one was contested against."""
    if vampire.contested_with is not None:
        raise ValueError(
            "remove_vampire_from_game: removing a contested vampire is unhandled -- "
            "see this function's own docstring"
        )
    vampire.zone = "removed_from_game"
    vampire.locked = False


def send_to_torpor(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Torpor: controlled but not ready (Rulebook SS4 Torpor).

    Dispatches `VAMPIRE_ENTERS_TORPOR_HOOK` (`hooks.run_effects`) immediately
    after the zone transition, for any card whose own text reacts to the
    moment a vampire goes to torpor (e.g. Fame, 100698, OQ-22). No provider
    was registered against this hook before OQ-22's own remaining clauses
    were wired, so this call changed no behaviour the instant it landed.
    """
    vampire.zone = "torpor"
    vampire.locked = False
    hooks.run_effects(VAMPIRE_ENTERS_TORPOR_HOOK, state, vampire=vampire, player=player)


def apply_damage(
    state: GameState,
    player: str,
    vampire: VampireInPlay,
    normal: int = 0,
    aggravated: int = 0,
    round_state: dict[str, Any] | None = None,
) -> None:
    """Resolve `normal` + `aggravated` damage against `vampire` (Rulebook SS4 Damage Resolution).

    Order: prevent (no prevention effects are implemented in this milestone;
    this is the hook point for future card-sourced prevention in
    `src/vtesbot/cards/`), then mend (voluntary, 1 blood per 1 point of
    *normal* damage only), then normal damage is resolved before aggravated.

    `round_state` (module docstring's "Round-scoped 'blood lost to damage'
    tracking" section, OQ-29 `docs/OPEN_QUESTIONS.md`): optional, the current
    round's shared scratch dict (`engine/combat.py::ROUND_STATE_CONTEXT_KEY`'s
    own object) -- when given, the Mend step and the aggravated-burn step
    below each record exactly how much blood *they themselves* spent via
    `record_blood_lost_to_damage`. `None` (every call site outside a combat
    round) is a no-op for this tracking, reproducing the previous, untracked
    behaviour exactly.
    """
    if normal < 0 or aggravated < 0:
        raise ValueError("damage amounts must be non-negative")
    if normal == 0 and aggravated == 0:
        return

    # --- Prevent step: single-sided window for the damaged vampire's own
    # controller (see module docstring); a "damage_box" is threaded through
    # so a registered prevention provider's `apply` can reduce it in place. ---
    damage_box = {"normal": normal, "aggravated": aggravated}
    hooks.offer_until_pass(
        state,
        DAMAGE_PREVENTION_HOOK,
        player,
        context={"vampire": vampire.instance_id, "damage": damage_box},
    )
    normal = max(0, damage_box["normal"])
    aggravated = max(0, damage_box["aggravated"])
    if normal == 0 and aggravated == 0:
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
        if vampire.zone == "burned":
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
