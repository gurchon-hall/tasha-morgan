"""Enchant Kindred (Action). krcg 100640. Snapshot: data/cards/100640.json
"Younger" than the acting vampire, by printed capacity (ENG-011); the target is
chosen at announce (RUL-007). Once per turn: ENG-037. Same text as Scouting Mission."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, discipline_level, has_discipline
from vtesbot.engine import effective_capacity
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.damage import add_blood
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import ActionCardPlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import (
    ActionCardSpec,
    action_card_already_played_this_turn,
    resolve_bleed,
)
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100640
NAME = "Enchant Kindred"
BASIC_BLEED_BASE_AMOUNT = 2  # the default 1, plus the printed +1
SUPERIOR_STEALTH = 1
ADD_BLOOD_AMOUNT = 2

card = Card(KRCG_ID, NAME, "Action")


def _eligible_targets(
    state: GameState, player: str, acting_vampire: VampireInPlay
) -> list[VampireInPlay]:
    return [
        v
        for v in state.players[player].vampires.values()
        if v.zone == "uncontrolled"
        and v.card.capacity < acting_vampire.card.capacity
        and effective_capacity(state, v) - v.blood > 0
    ]


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_enchant_kindred_basic(
    state: GameState, ctx: ActionCardPlayContext
) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or not has_discipline(state, vampire, "pre"):
        return []
    if not card.in_hand(state, player):
        return []
    if action_card_already_played_this_turn(state, vampire, NAME):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)

        def resolve(pending: dict[str, Any]) -> None:
            resolve_bleed(s, player, vampire, BASIC_BLEED_BASE_AMOUNT, pending)

        return ActionCardSpec(
            base_stealth=0, directed=True, resolve=resolve, action=ACTION_BLEED, name=NAME
        )

    return [
        card.option("enchant_kindred:basic", "Enchant Kindred [pre]: Bleed with +1 bleed", _apply)
    ]


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_enchant_kindred_superior(
    state: GameState, ctx: ActionCardPlayContext
) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or discipline_level(state, vampire, "pre") < 2:
        return []
    if not card.in_hand(state, player) or not _eligible_targets(state, player, vampire):
        return []
    if action_card_already_played_this_turn(state, vampire, NAME):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)
        targets = _eligible_targets(s, player, vampire)
        if len(targets) == 1:
            target_id = targets[0].instance_id
        else:
            choices = tuple(
                Choice(f"enchant_kindred_target:{v.instance_id}", f"Add 2 blood to {v.card.name}")
                for v in targets
            )
            decision = Decision(player=player, kind="enchant_kindred_target", choices=choices)
            target_id = s.ask(decision).value.split(":", 1)[1]

        def resolve(_pending: dict[str, Any]) -> None:
            target = s.players[player].vampires.get(target_id)
            if target is None or target not in _eligible_targets(s, player, vampire):
                return  # fizzles (RUL-007)
            add_blood(s, target, ADD_BLOOD_AMOUNT)

        return ActionCardSpec(
            base_stealth=SUPERIOR_STEALTH, directed=False, resolve=resolve, name=NAME
        )

    return [
        card.option(
            "enchant_kindred:superior",
            "Enchant Kindred [PRE]: +1 stealth action. "
            "Add 2 blood to a younger vampire in your uncontrolled region",
            _apply,
        )
    ]
