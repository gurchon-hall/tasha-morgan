"""Dust Up (Combat). krcg 100597. Snapshot: data/cards/100597.json

Text: "Requires an Anarch.
[ani] Strike: hand strike at +1 damage. This strike cannot be dodged.
[cel] Strike: dodge, with 1 additional strike (limited).
[pot] Strike: hand strike at +2 damage."

Rulings:
- [TOM 19960225] "[ani] [pot] Additional damage inherits all of the
  properties of the base damage." Both strikes are built from
  `hand_strike_damage` with `dataclasses.replace` (ENG-048).
- [ANK 20220204] [cel] the additional strike is not optional, so the
  "(limited)" cap gates the dodge itself.
- [LSJ 20011204-3] [PIB 20130704] when played, the card requires the
  discipline being used; in hand, library or ash heap it requires any and
  all of [ani] [cel] [pot].
- [LSJ 20030902-2] [LSJ 20060808-1] [ani] the opponent may still dodge; the
  dodge has no effect (`StrikeDamage.ignore_dodge`).

Notes:
- "Requires an Anarch": `vampire.card.sect is Sect.ANARCH`; an unknown sect
  (`None`) does not qualify (ENG-012).
- [cel] is a dodge option recording a per-vampire grant in `round_state`,
  claimed through `COMBAT_ADDITIONAL_STRIKE`; the "(limited)" cap is shared
  across cards and resets each round (ENG-013).
"""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, has_discipline
from vtesbot.engine.cards import Sect
from vtesbot.engine.combat import (
    COMBAT_STATE_CONTEXT_KEY,
    StrikeDamage,
    additional_strike_limit_used,
    hand_strike_damage,
    mark_additional_strike_limit_used,
)
from vtesbot.engine.hook_contexts import (
    CombatAdditionalStrikeContext,
    CombatDodgeOptionContext,
    CombatStrikeOptionContext,
)
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 100597
CEL_GRANTS_KEY = "dust_up_cel_grants"
"""`round_state[CEL_GRANTS_KEY]`: vampire id -> unclaimed [cel] grant."""

card = Card(KRCG_ID, "Dust Up", "Combat")


def _playable(state: GameState, ctx: Mapping[str, Any], discipline: str) -> bool:
    vampire = context_vampire(state, ctx)
    return (
        vampire is not None
        and vampire.card.sect is Sect.ANARCH
        and has_discipline(state, vampire, discipline)
        and card.in_hand(state, ctx["player"])
    )


def _base_damage(state: GameState, ctx: Mapping[str, Any]) -> StrikeDamage:
    return hand_strike_damage(
        state, ctx["player"], ctx["vampire"], ctx["opponent"], ctx.get(COMBAT_STATE_CONTEXT_KEY)
    )


def _has_grant(round_state: dict[str, Any] | None, vampire_id: str) -> bool:
    """A missing `round_state` (hook probed outside `run_combat`) holds no grant."""
    return round_state is not None and bool(round_state.get(CEL_GRANTS_KEY, {}).get(vampire_id))


def _set_grant(round_state: dict[str, Any] | None, vampire_id: str, value: bool) -> None:
    if round_state is not None:
        round_state.setdefault(CEL_GRANTS_KEY, {})[vampire_id] = value


@card.on(Hook.COMBAT_STRIKE_OPTION)
def _ani_strike(state: GameState, ctx: CombatStrikeOptionContext) -> list[HookOption]:
    if not _playable(state, ctx, "ani"):
        return []
    player, base = ctx["player"], _base_damage(state, ctx)

    def apply(s: GameState) -> StrikeDamage:
        card.play_from_hand(s, player)
        return replace(base, amount=base.amount + 1, ignore_dodge=True)

    return [card.option("dust_up:ani", "Dust Up [ani]: hand strike +1, cannot be dodged", apply)]


@card.on(Hook.COMBAT_STRIKE_OPTION)
def _pot_strike(state: GameState, ctx: CombatStrikeOptionContext) -> list[HookOption]:
    if not _playable(state, ctx, "pot"):
        return []
    player, base = ctx["player"], _base_damage(state, ctx)

    def apply(s: GameState) -> StrikeDamage:
        card.play_from_hand(s, player)
        return replace(base, amount=base.amount + 2)

    return [card.option("dust_up:pot", "Dust Up [pot]: hand strike +2 damage", apply)]


@card.on(Hook.COMBAT_DODGE_OPTION)
def _cel_dodge(state: GameState, ctx: CombatDodgeOptionContext) -> list[HookOption]:
    if not _playable(state, ctx, "cel") or additional_strike_limit_used(ctx):
        return []
    player, vampire_id, round_state = ctx["player"], ctx["vampire"], ctx.get("round_state")

    def apply(s: GameState) -> None:
        card.play_from_hand(s, player)
        mark_additional_strike_limit_used(ctx)
        _set_grant(round_state, vampire_id, True)

    return [
        card.option(
            "dust_up:cel", "Dust Up [cel]: dodge, with 1 additional strike (limited)", apply
        )
    ]


@card.on(Hook.COMBAT_ADDITIONAL_STRIKE)
def _cel_additional_strike(
    state: GameState, ctx: CombatAdditionalStrikeContext
) -> list[HookOption]:
    """Claims the grant; the "(limited)" cap was checked when it was granted."""
    vampire_id, round_state = ctx["vampire"], ctx.get("round_state")
    if context_vampire(state, ctx) is None or not _has_grant(round_state, vampire_id):
        return []

    def apply(s: GameState) -> None:
        _set_grant(round_state, vampire_id, False)

    return [
        card.option(
            "dust_up:cel_additional_strike",
            "Dust Up [cel]: use the granted additional strike",
            apply,
            played_card_type=None,  # claims a grant; the card was played at the dodge
        )
    ]
