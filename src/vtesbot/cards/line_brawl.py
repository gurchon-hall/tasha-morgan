"""Line Brawl (Action). krcg 102229. Snapshot: data/cards/102229.json
Three directed clauses, one per discipline. [pot] targets any ready opposing
vampire, left unlocked, chosen at announce (RUL-007). Once per turn: ENG-037."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, has_discipline
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.cards import Sect
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import ActionCardPlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import (
    ActionCardSpec,
    action_card_already_played_this_turn,
    build_enter_combat_action_spec,
    resolve_bleed,
)
from vtesbot.engine.pool import gain_pool, lose_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 102229
NAME = "Line Brawl"
STEAL_AMOUNT = 1
PRE_BLEED_BASE_AMOUNT = 2  # the default 1, plus the printed +1

card = Card(KRCG_ID, NAME, "Action")


def _playable(
    state: GameState, ctx: ActionCardPlayContext, discipline: str
) -> VampireInPlay | None:
    """The acting vampire if this Anarch may play the `discipline` clause."""
    vampire = context_vampire(state, ctx)
    if vampire is None or vampire.card.sect is not Sect.ANARCH:
        return None
    if not has_discipline(state, vampire, discipline) or not card.in_hand(state, ctx["player"]):
        return None
    return vampire


def _eligible_combat_targets(state: GameState, player: str) -> list[VampireInPlay]:
    """Ready opposing vampires; allies are outside the engine's combat scope."""
    opponent = state.other_player(player)
    return [v for v in state.players[opponent].vampires.values() if v.zone == "ready"]


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_line_brawl_cel(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    """A pool transfer, not a bleed: no Edge."""
    player, vampire = ctx["player"], _playable(state, ctx, "cel")
    if vampire is None or action_card_already_played_this_turn(state, vampire, NAME):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)

        def resolve(_pending: dict[str, Any]) -> None:
            stolen = lose_pool(s, s.other_player(player), STEAL_AMOUNT)
            gain_pool(s, player, stolen)

        return ActionCardSpec(base_stealth=0, directed=True, resolve=resolve, name=NAME)

    return [
        card.option(
            "line_brawl:cel", "Line Brawl [cel]: Steal 1 pool from another Methuselah", _apply
        )
    ]


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_line_brawl_pot(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    """Blocked, the block's own combat is the clause's combat."""
    player, vampire = ctx["player"], _playable(state, ctx, "pot")
    if vampire is None or not _eligible_combat_targets(state, player):
        return []
    if action_card_already_played_this_turn(state, vampire, NAME):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)
        targets = _eligible_combat_targets(s, player)
        if len(targets) == 1:
            target_id = targets[0].instance_id
        else:
            choices = tuple(
                Choice(
                    f"line_brawl_combat_target:{v.instance_id}", f"Enter combat with {v.card.name}"
                )
                for v in targets
            )
            decision = Decision(player=player, kind="line_brawl_combat_target", choices=choices)
            target_id = s.ask(decision).value.split(":", 1)[1]
        return build_enter_combat_action_spec(
            s, player, vampire, s.other_player(player), target_id, name=NAME
        )

    return [card.option("line_brawl:pot", "Line Brawl [pot]: Enter combat with a minion", _apply)]


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_line_brawl_pre(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    player, vampire = ctx["player"], _playable(state, ctx, "pre")
    if vampire is None or action_card_already_played_this_turn(state, vampire, NAME):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)

        def resolve(pending: dict[str, Any]) -> None:
            resolve_bleed(s, player, vampire, PRE_BLEED_BASE_AMOUNT, pending)

        return ActionCardSpec(
            base_stealth=0, directed=True, resolve=resolve, action=ACTION_BLEED, name=NAME
        )

    return [card.option("line_brawl:pre", "Line Brawl [pre]: Bleed with +1 bleed", _apply)]
