"""Fleetness (Action). krcg 100747. Snapshot: data/cards/100747.json
"+1 stealth" and the 1 blood (paid on success) cover both clauses. [CEL] picks its
target at announce; an unlocked one fizzles, cost paid [ANK 20210124]. See ENG-017."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, discipline_level
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.combat import (
    consume_pre_combat_maneuver_grant,
    pre_combat_maneuver_available,
    run_combat,
    seed_pre_combat_maneuver_grant,
)
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import ActionCardPlayContext, ManeuverContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import (
    BLEED_AMOUNT,
    ActionCardSpec,
    action_card_already_played_this_turn,
    resolve_bleed,
)
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100747
NAME = "Fleetness"
STEALTH = 1
BLOOD_COST = 1

card = Card(KRCG_ID, NAME, "Action")


def _eligible_locked_targets(state: GameState, player: str) -> list[VampireInPlay]:
    opponent = state.other_player(player)
    return [v for v in state.players[opponent].vampires.values() if v.zone == "ready" and v.locked]


def _playable(state: GameState, ctx: ActionCardPlayContext, level: int) -> VampireInPlay | None:
    """The acting vampire if it may play the card at `level` (1 or 2)."""
    vampire = context_vampire(state, ctx)
    if vampire is None or discipline_level(state, vampire, "cel") < level:
        return None
    if not card.in_hand(state, ctx["player"]) or vampire.blood < BLOOD_COST:
        return None
    return vampire


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_fleetness_basic(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    player, vampire = ctx["player"], _playable(state, ctx, 1)
    if vampire is None or action_card_already_played_this_turn(state, vampire, NAME):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)

        def resolve(pending: dict[str, Any]) -> None:
            vampire.blood -= BLOOD_COST
            resolve_bleed(s, player, vampire, BLEED_AMOUNT, pending)

        return ActionCardSpec(
            base_stealth=STEALTH, directed=True, resolve=resolve, action=ACTION_BLEED, name=NAME
        )

    return [card.option("fleetness:basic", "Fleetness [cel]: +1 stealth action. Bleed", _apply)]


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_fleetness_superior(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    player, vampire = ctx["player"], _playable(state, ctx, 2)
    if vampire is None or not _eligible_locked_targets(state, player):
        return []
    if action_card_already_played_this_turn(state, vampire, NAME):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)
        opponent = s.other_player(player)
        targets = _eligible_locked_targets(s, player)
        if len(targets) == 1:
            target_id = targets[0].instance_id
        else:
            choices = tuple(
                Choice(
                    f"fleetness_combat_target:{v.instance_id}", f"Enter combat with {v.card.name}"
                )
                for v in targets
            )
            decision = Decision(player=player, kind="fleetness_combat_target", choices=choices)
            target_id = s.ask(decision).value.split(":", 1)[1]

        def resolve(_pending: dict[str, Any]) -> None:
            vampire.blood -= BLOOD_COST
            target = s.players[opponent].vampires.get(target_id)
            if target is None or target.zone != "ready" or not target.locked:
                return  # fizzles
            run_combat(
                s,
                player,
                vampire,
                opponent,
                target,
                seed_pre_combat_maneuver_grant(vampire.instance_id),
            )

        return ActionCardSpec(
            base_stealth=STEALTH,
            directed=True,
            resolve=resolve,
            maneuver_grant=vampire.instance_id,
            name=NAME,
        )

    return [
        card.option(
            "fleetness:superior",
            "Fleetness [CEL]: +1 stealth action. "
            "Enter combat with a locked minion. Gets 1 optional maneuver",
            _apply,
        )
    ]


@card.on(Hook.MANEUVER)
def _provide_fleetness_maneuver(state: GameState, ctx: ManeuverContext) -> list[HookOption]:
    if not pre_combat_maneuver_available(ctx):
        return []

    def _use(_s: GameState) -> None:
        consume_pre_combat_maneuver_grant(ctx)

    return [
        card.option(
            "fleetness:maneuver",
            "Fleetness: optional maneuver",
            _use,
            played_card_type=None,  # claims the grant; the card was played as the action
        )
    ]
