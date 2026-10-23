"""Dominate Kine (Action). krcg 100573. Snapshot: data/cards/100573.json
"+1 stealth" sits on the [dom] line only. 2 blood paid on success only (Rulebook
§4); the location is chosen at announce (RUL-007). Once per turn: ENG-037."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, discipline_level, has_discipline
from vtesbot.cards.disputed_territory import LOCATION_KRCG_IDS
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import ActionCardPlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.master_cards import transfer_master_card_control
from vtesbot.engine.phases.minion import (
    ActionCardSpec,
    action_card_already_played_this_turn,
    resolve_bleed,
)
from vtesbot.engine.state import GameState, MasterCardInPlay

KRCG_ID = 100573
NAME = "Dominate Kine"
BASIC_STEALTH = 1
BASIC_BLEED_BASE_AMOUNT = 2  # the default 1, plus the printed +1
BLOOD_COST = 2

card = Card(KRCG_ID, NAME, "Action")


def _opponent_in_play_locations(state: GameState, opponent: str) -> list[MasterCardInPlay]:
    return [
        location
        for location in state.players[opponent].master_cards.values()
        if location.krcg_id in LOCATION_KRCG_IDS and location.zone == "in_play"
    ]


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_dominate_kine_basic(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or not has_discipline(state, vampire, "dom"):
        return []
    if not card.in_hand(state, player) or vampire.blood < BLOOD_COST:
        return []
    if action_card_already_played_this_turn(state, vampire, NAME):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)

        def resolve(pending: dict[str, Any]) -> None:
            vampire.blood -= BLOOD_COST
            resolve_bleed(s, player, vampire, BASIC_BLEED_BASE_AMOUNT, pending)

        return ActionCardSpec(
            base_stealth=BASIC_STEALTH,
            directed=True,
            resolve=resolve,
            action=ACTION_BLEED,
            name=NAME,
        )

    return [
        card.option(
            "dominate_kine:basic",
            "Dominate Kine [dom]: +1 stealth action. Bleed with +1 bleed",
            _apply,
        )
    ]


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_dominate_kine_superior(
    state: GameState, ctx: ActionCardPlayContext
) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or discipline_level(state, vampire, "dom") < 2:
        return []
    if not card.in_hand(state, player) or vampire.blood < BLOOD_COST:
        return []
    opponent = state.other_player(player)
    if not _opponent_in_play_locations(state, opponent):
        return []
    if action_card_already_played_this_turn(state, vampire, NAME):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)
        locations = _opponent_in_play_locations(s, opponent)
        if len(locations) == 1:
            target_id = locations[0].instance_id
        else:
            choices = tuple(
                Choice(f"dominate_kine_target:{location.instance_id}", f"Steal {location.name}")
                for location in locations
            )
            decision = Decision(player=player, kind="dominate_kine_target", choices=choices)
            target_id = s.ask(decision).value.split(":", 1)[1]

        def resolve(_pending: dict[str, Any]) -> None:
            vampire.blood -= BLOOD_COST
            location = s.players[opponent].master_cards.get(target_id)
            if (
                location is None
                or location.controller != opponent
                or location.zone != "in_play"
                or location.krcg_id not in LOCATION_KRCG_IDS
            ):
                return  # fizzles (RUL-007)
            transfer_master_card_control(s, location, player)

        return ActionCardSpec(base_stealth=0, directed=True, resolve=resolve, name=NAME)

    return [card.option("dominate_kine:superior", "Dominate Kine [DOM]: steal a location", _apply)]
