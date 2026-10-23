"""Disputed Territory (Political Action). krcg 100557. Snapshot: data/cards/100557.json
Either Methuselah may receive it. Only "Unique location." masters are recognised,
not equipment locations (ENG-063); terms come after the vote, not before (ENG-062)."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.action import ACTION_POLITICAL
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import ActionCardPlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.master_cards import transfer_master_card_control
from vtesbot.engine.phases.minion import ActionCardSpec, action_card_already_played_this_turn
from vtesbot.engine.politics import POLITICAL_ACTION_STEALTH, resolve_referendum
from vtesbot.engine.state import GameState, MasterCardInPlay

KRCG_ID = 100557
NAME = "Disputed Territory"

LOCATION_KRCG_IDS = frozenset(
    {
        100135,  # The Barrens
        100329,  # Chantry
        100594,  # Dummy Corporation
        100620,  # Elder Library
        101110,  # The Line
        101341,  # Oxford University, England
        101552,  # Ravnos Cache
        101553,  # Ravnos Carnival
        101662,  # The Rumor Mill, Tabloid Newspaper
        102152,  # Wasserschloss Anif, Austria
        102189,  # WMRH Talk Radio
        102301,  # Powerbase: Munich
        102313,  # Cursed Abattoir
        102354,  # Fleshforge Chamber
    }
)
"""Every "Unique location." master on the active 2P list; a test re-sweeps it."""

card = Card(KRCG_ID, NAME, "Political Action")


def _in_play_locations(state: GameState) -> list[MasterCardInPlay]:
    return [
        location
        for player_state in state.players.values()
        for location in player_state.master_cards.values()
        if location.krcg_id in LOCATION_KRCG_IDS and location.zone == "in_play"
    ]


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_disputed_territory(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    """Not offered with no location in play [LSJ 20100129]."""
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or not card.in_hand(state, player):
        return []
    if not _in_play_locations(state):
        return []
    if action_card_already_played_this_turn(state, vampire, NAME):
        return []
    other = state.other_player(player)

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)

        def resolve(pending: dict[str, Any]) -> None:
            votes_for, votes_against, _casts = resolve_referendum(
                s, player, other, vampire, action_pending=pending
            )
            if s.game_over or votes_for <= votes_against:
                return  # ousted at tally (ENG-052), or failed (ties fail)
            locations = _in_play_locations(s)
            if not locations:
                return
            choices = tuple(
                Choice(
                    f"transfer:{location.instance_id}:{new_controller}",
                    f"Give {new_controller} control of {location.name}",
                )
                for location in locations
                for new_controller in (player, other)
            )
            decision = Decision(
                player=player,
                kind="disputed_territory_terms",
                choices=choices,
                context={"caller": player, "other": other},
            )
            _prefix, instance_id, new_controller = s.ask(decision).value.split(":", 2)
            location = next(c for c in locations if c.instance_id == instance_id)
            transfer_master_card_control(s, location, new_controller)

        return ActionCardSpec(
            base_stealth=POLITICAL_ACTION_STEALTH,
            directed=False,
            action=ACTION_POLITICAL,
            resolve=resolve,
            name=NAME,
        )

    return [card.option("disputed_territory:play", f"Play {NAME}", _apply)]
