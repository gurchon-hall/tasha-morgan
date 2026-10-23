"""Dust Up (Combat). krcg 100597. Snapshot: data/cards/100597.json
"Requires an Anarch": an unknown sect does not qualify (ENG-012). [cel] is one
choice [ANK 20220204]: the dodge records a grant (ENG-013); damage per ENG-048."""

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
    """Played, it requires only the discipline used [LSJ 20011204-3]."""
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
    """A dodge does not stop it [LSJ 20030902-2]."""
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
