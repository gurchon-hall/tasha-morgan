"""Damage resolution: prevent, mend (normal only), wounded->torpor->burn (§4). Aggravated
wounds+torpors a healthy vampire in one step. OQ-29: round-scoped blood-lost tracking for
Taste of Vitae."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from . import hooks
from .attachments import effective_capacity
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

DAMAGE_PREVENTION_HOOK = "damage_prevention"
VAMPIRE_ENTERS_TORPOR_HOOK = "vampire_enters_torpor"
"""Mandatory reaction hook, dispatched by `send_to_torpor` (OQ-22, Fame). Passes the live
`VampireInPlay`, safe since `run_effects` only runs trusted card code."""


BLOOD_LOST_TO_DAMAGE_KEY = "blood_lost_to_damage"
"""Key in the round-scoped scratch dict (OQ-29): per vampire id, blood lost this round
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
    """Blood `vampire_id` lost to damage this round (OQ-29 query helper, e.g. Taste of
    Vitae). `round_state` is caller-supplied to avoid a circular import; `None` -> 0."""
    if round_state is None:
        return 0
    return round_state.get(BLOOD_LOST_TO_DAMAGE_KEY, {}).get(vampire_id, 0)


def add_blood(state: GameState, vampire: VampireInPlay, amount: int) -> int:
    """Add blood to a vampire, capped at its effective capacity (§1, OQ-8). Returns the
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
    """Remove a crypt card from the game (OQ-24; Wider View, 102180). Distinct zone from
    `burn_vampire` (see `VampireInPlay`). Guards against removing a contested vampire,
    unreachable today (OQ-24 addendum)."""
    if vampire.contested_with is not None:
        raise ValueError(
            "remove_vampire_from_game: removing a contested vampire is unhandled -- "
            "see this function's own docstring"
        )
    vampire.zone = "removed_from_game"
    vampire.locked = False


def send_to_torpor(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Torpor: controlled but not ready (§4 Torpor). Dispatches
    `VAMPIRE_ENTERS_TORPOR_HOOK` after the zone transition (OQ-22, Fame)."""
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
) -> None:
    """Resolve `normal` + `aggravated` damage (§4). Order: prevent, mend (normal only),
    normal before aggravated. `round_state` (OQ-29) records blood spent when given;
    `None` is a no-op."""
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
    hooks.offer_until_pass(
        state,
        DAMAGE_PREVENTION_HOOK,
        player,
        context={"vampire": vampire.instance_id, "damage": damage_box},
    )
    normal = max(0, damage_box["normal"])
    aggravated = max(0, damage_box["aggravated"])
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
