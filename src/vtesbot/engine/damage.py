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
"""

from typing import TYPE_CHECKING

from . import hooks
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

DAMAGE_PREVENTION_HOOK = "damage_prevention"


def add_blood(vampire: VampireInPlay, amount: int) -> int:
    """Add blood to a vampire, capped at its capacity (Rulebook SS1 Vampires).

    Returns the amount actually added.
    """
    if amount <= 0:
        return 0
    added = min(amount, vampire.card.capacity - vampire.blood)
    vampire.blood += added
    return added


def burn_vampire(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Move a vampire out of play to the ash heap (destroyed)."""
    vampire.zone = "burned"
    vampire.locked = False


def send_to_torpor(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Torpor: controlled but not ready (Rulebook SS4 Torpor)."""
    vampire.zone = "torpor"
    vampire.locked = False


def apply_damage(
    state: GameState,
    player: str,
    vampire: VampireInPlay,
    normal: int = 0,
    aggravated: int = 0,
) -> None:
    """Resolve `normal` + `aggravated` damage against `vampire` (Rulebook SS4 Damage Resolution).

    Order: prevent (no prevention effects are implemented in this milestone;
    this is the hook point for future card-sourced prevention in
    `src/vtesbot/cards/`), then mend (voluntary, 1 blood per 1 point of
    *normal* damage only), then normal damage is resolved before aggravated.
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
            else:
                burn_vampire(state, player, vampire)
        else:
            # First aggravated point against a healthy vampire: wounds AND
            # sends straight to torpor (Nassir/Tamoszius worked examples;
            # unlike normal damage, there is no "merely wounded" state for
            # a healthy vampire taking aggravated damage).
            vampire.wounded = True
            send_to_torpor(state, player, vampire)
