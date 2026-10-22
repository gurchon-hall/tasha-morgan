"""Disputed Territory (Political Action). krcg id 100557.

Card text (verbatim, re-verified live via the installed `krcg` package,
`krcg.vtes.VTES["Disputed Territory"]`, 2026-10-14, matching the docstring
already on file):
    "Choose a location and a Methuselah. Successful referendum means the
    chosen Methuselah takes control of the chosen location."
`types == ["Political Action"]`, `clans == []`, `disciplines == []`,
`requirement is None`, `pool_cost is None` -- no requirement or cost beyond
playing a Political Action card at all, the same shape as Kine Resources
Contested.

Rulings (verbatim, via krcg):
    - "Requirements do not apply when taking control of a card already in
      play." [TOM 19960226-1]
    - "If used to steal an equipment representing a location, it can be
      placed on any minion controlled by the new controller." [RTR 19960112]
    - "If used to 'change' the control of a location or equipment
      representing a location to the same Methuselah, the location cannot
      be moved to another minion controlled by the same Methuselah."
      [LSJ 19971002]
    - "Changing the controller of a location has no other effect, unless
      specified by card text. Exception: A location 'on' another controlled
      card is moved onto an appropriate card controlled by the new
      controller of the location." [RTR 19980623]
    - "Cannot be used or played if the conditions for the terms of the
      referendum cannot be met (e.g. no legal selection, insufficient
      cards/players to choose from, prohibited by card text, uniqueness,
      etc)." [LSJ 20100129] [ANK 20191228]

Engine wiring: mirrors `kine_resources_contested.py`'s use of
`ACTION_CARD_PLAY_HOOK`/`ActionCardSpec` (`rules-auditor`'s note on file:
`engine/politics.py::political_action` is not the right entry point --
see that module's own docstring). `directed=False`: unlike Parity Shift's
"Choose a Methuselah who has more pool than you do" (a named victim, fixed
at announce), neither "a location" nor "a Methuselah" here names anything
that determines who may block -- this is a plain undirected political
action, and (Rulebook §4 "Politics": "Terms chosen only after success")
both choices are the referendum's own terms, picked by the caller only once
`resolve_referendum` reports a pass, as a fresh `"disputed_territory_terms"`
`Decision` raised inside `resolve()` (mirrors Kine Resources Contested's
allocation decision, not Parity Shift's announce-time target).

ENG-037: calls `remove_from_hand` (not
`play_from_hand`) and sets `ActionCardSpec.name=NAME`, so `_perform_
action_card` can interleave a future Reflex card's own cancel-as-played
window before drawing the replacement (Finding 1), and so a second
physical copy is not offered once this card has already been played this
turn (Finding 2).

"A location": ENG-015 already found this is free text on a card, not a krcg
type. A krcg sweep (re-verified live 2026-10-14, every active-2P-list id
whose `card_text` starts with "Unique location.") found the shape splits
into two kinds of in-play entity (ENG-025's own two primitives), but only one
is reachable in the active 2P pool (`data/formats/2p/2026-10-03.json`,
re-checked directly): 14 standalone "Unique location." Master cards
(`LOCATION_KRCG_IDS` below -- `rules-auditor` finding: an earlier draft of
this constant held only 4, an undercount from an incomplete first sweep);
every "equipment representing a location" card found live (Pier 13,
Inveraray, Dartmoor, Ankara Citadel, Living Manse, Local 1111, Lyndhurst
Estate, Ruins of Ceoris/Villers Abbey, Sacre-Coeur Cathedral, Winchester
Mansion, San Lorenzo/San Nicolas, Zaire River Ferry, Catacombs, Palatial
Estate, Gran Madre di Dio) is absent from the 2P list. So only
`engine/master_cards.py::transfer_master_card_control` is wired here;
`engine/attachments.py::transfer_attachment_control` (the re-host half,
covering the "equipment representing a location"/[RTR 19960112]/
[LSJ 19971002] rulings) is exercised instead at the engine level by
`tests/rules/test_location_control_transfer.py` -- if a future 2P list
update adds one of the cards above, this module needs a second branch.
`tests/cards/test_disputed_territory.py::
test_location_krcg_ids_matches_a_fresh_krcg_sweep_of_the_active_2p_list` is
a tripwire against this exact drift: it re-runs the sweep live and fails if
`LOCATION_KRCG_IDS` and the 2P list ever disagree again, catching both a
stale undercount and a future 2P-list addition.
"Requirements do not apply ...": satisfied for free, since
`transfer_master_card_control` checks no requirement at all.

"A Methuselah": the text names no restriction on the recipient (neither
caller nor opponent is excluded, nor must they differ from the current
controller -- [LSJ 19971002]'s "cannot be moved to another minion" is
scoped to the re-host-only attachment shape, moot here since a standalone
card is never "on" a minion to begin with), so both Methuselahs are always
offered as the recipient for every eligible location.

"Cannot be used ... if no legal selection": gated at offer time on "is at
least one `LOCATION_KRCG_IDS` card currently `zone == 'in_play'`" (across
either player); if none, the card is not offered at all, mirroring Parity
Shift's "no legal target" gate.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import remove_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_POLITICAL
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.master_cards import transfer_master_card_control
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    ActionCardSpec,
    action_card_already_played_this_turn,
)
from vtesbot.engine.politics import POLITICAL_ACTION_STEALTH, resolve_referendum
from vtesbot.engine.state import GameState, MasterCardInPlay

KRCG_ID = 100557
NAME = "Disputed Territory"
CARD_TYPE = "Political Action"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Political Action" docstring fact above."""

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
"""Every standalone "Unique location." Master card on the active 2P list
(module docstring) -- 14, not the 4 an earlier draft held. Only Oxford
University, England has its own card module today
(`cards/oxford_university_england.py`); the rest stay unimplemented, so in
practice only a brought-in Oxford instance can ever be a live target --
this set is not narrowed to just that id, so a future card module for any
of the others needs no change here."""


def _in_play_locations(state: GameState) -> list[MasterCardInPlay]:
    return [
        card
        for player_state in state.players.values()
        for card in player_state.master_cards.values()
        if card.krcg_id in LOCATION_KRCG_IDS and card.zone == "in_play"
    ]


def _provide_disputed_territory(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    acting_vampire_id = context["vampire"]
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None:
        return []  # `player` is the defender this window, not the acting player.
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if not _in_play_locations(state):
        # "Cannot be used or played if ... no legal selection" -- no location
        # at all is currently in play, on either side.
        return []
    if action_card_already_played_this_turn(state, acting_vampire, NAME):
        return []  # ENG-037 Finding 2: same named action card, once per turn.

    other = state.other_player(player)

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            votes_for, votes_against, _casts = resolve_referendum(
                s, player, other, acting_vampire, action_pending=pending
            )
            if votes_for <= votes_against:
                return  # referendum fails ("tied referendums fail"): no effect at all.

            locations = _in_play_locations(s)
            if not locations:
                return  # no legal selection left by resolve time: no effect.

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
            answer = s.ask(decision).value
            _prefix, instance_id, new_controller = answer.split(":", 2)
            location = next(c for c in locations if c.instance_id == instance_id)
            transfer_master_card_control(s, location, new_controller)

        return ActionCardSpec(
            base_stealth=POLITICAL_ACTION_STEALTH,
            directed=False,
            action=ACTION_POLITICAL,
            resolve=resolve,
            name=NAME,
        )

    return [
        HookOption(
            choice=Choice("disputed_territory:play", f"Play {NAME}"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_disputed_territory)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
