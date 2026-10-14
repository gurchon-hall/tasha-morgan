"""Loup (Action Modifier). krcg id 102273.

Card text (verbatim, via the installed `krcg` package's
`krcg.vtes.VTES['Loup'].card_text`, re-verified live 2026-10-14, matching
the raw snapshot `data/cards/102273.json`): "Only one Loup can be played
each turn.\nPut this card in play. Toreador get +1 stealth. Burn this card
at the end of the turn or after a Toreador performs a successful action."
Clan Toreador (`clans == ["Toreador"]`); no discipline requirement, no cost.

Ruling (verbatim, via krcg): "Can be used even if the stealth is not
currently needed. [LSJ 20011214-2]."

Built on OQ-34's own primitives (`docs/OPEN_QUESTIONS.md`, resolved):
`engine/turn_cards.py` (`TurnCardInPlay`/`bring_turn_card_into_play`/
`burn_turn_card`/`active_turn_cards`) and `engine/action.py::
ACTION_SUCCEEDED_HOOK`. Both clauses -- the clan-wide grant and burn
condition 2 -- bind to the *controller's own* Toreador vampires, never the
opponent's: `STEALTH_MODIFIER_HOOK` is only ever offered to the acting
player for their own action (`context["player"]`/`context["acting_vampire"]`
are always that player's own), and `_provide_loup_burn` below only ever
checks `active_turn_cards(state, context["actor_player"], KRCG_ID)` --
`context["actor_player"]`'s own turn cards, never a cross-player lookup.

One provider, registered against `STEALTH_MODIFIER_HOOK` (`engine/
action.py`), does double duty, gated throughout on the acting vampire
(`context["acting_vampire"]`, re-resolved fresh every call -- same "bind to
the specific acting minion" precedent as `forty_seventh_street_royals.py::
_provide_recruit`, OQ-13) being Toreador -- Rulebook SS2 "Requirements for
Playing Cards": "Only a minion who meets the requirements given on a minion
card can play it":
  - no copy currently `is_in_play` for this player: offers "play a copy
    from hand", additionally gated on the "only one Loup can be played
    each turn" cap (`PlayerState.card_played_turn`, `engine/state.py`, a
    new generic field added by this pass, mirroring `VampireInPlay.
    ability_used_turn`'s own shape but scoped to the controller, since this
    cap is a plain card-play restriction, not a specific minion's ability);
  - a copy already `is_in_play`: offers the ongoing "+1 stealth" grant
    itself, with no re-play and no cost (plain passive bonus, same
    `played_card_type=None` reasoning as `maila.py`'s own ability
    activation -- this option is not a card being played).

Known gap, not modeled: the on-file ruling's full generality ("even if the
stealth is not currently needed") exempts Loup from the Rulebook's general
default stealth-timing rule ("Stealth can be added during an action only
when needed, that is, only if the action is currently being blocked and the
blocking minion has enough intercept" -- `data/sources/rulebook/2026-10-09/
4-detailed-turn-sequence.md:559-561`) -- but `STEALTH_MODIFIER_HOOK` is only
ever offered from within that very "only when needed" ping-pong (`engine/
action.py::_duel_stealth_intercept`), never when no block attempt happens at
all, or while stealth already strictly exceeds intercept pre-modifier.
Reaching those cases would need a new engine primitive (e.g. a
`pending`-based proactive stealth-addition accumulator, mirroring
`INTERCEPT_DECREASE_HOOK`'s own OQ-30/31 shape) -- a `rules-engineer` job,
flagged here rather than guessed around (same precedent as OQ-32's own
"flagged for whoever wires their dispatch sites through it next"). This
module never mis-resolves within the window it *does* reach: the gap only
ever means fewer opportunities to use the card than a maximally permissive
reading would offer, never an incorrect application.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand_pending
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_SUCCEEDED_HOOK, STEALTH_MODIFIER_HOOK
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay
from vtesbot.engine.turn_cards import active_turn_cards, bring_turn_card_into_play, burn_turn_card

KRCG_ID = 102273
NAME = "Loup"
CLAN_REQUIREMENT = "Toreador"
CARD_TYPE = "Action Modifier"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Action Modifier" docstring fact -- set only on
the play-from-hand option (the card actually leaving hand); the ongoing
"+1 stealth" grant leaves it at its default `None` (module docstring)."""


def _acting_vampire(
    state: GameState, player: str, context: Mapping[str, Any]
) -> VampireInPlay | None:
    vampire_id = context.get("acting_vampire")
    if vampire_id is None:
        return None
    return state.players[player].vampires.get(vampire_id)


def _provide_loup(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    acting_vampire = _acting_vampire(state, player, context)
    if acting_vampire is None or acting_vampire.card.clan != CLAN_REQUIREMENT:
        return []

    if active_turn_cards(state, player, KRCG_ID):

        def _apply_bonus(s: GameState) -> int:
            del s
            return 1

        return [
            HookOption(
                choice=Choice("loup:stealth_bonus", "Loup: Toreador get +1 stealth"),
                apply=_apply_bonus,
            )
        ]

    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if state.players[player].card_played_turn.get(KRCG_ID) == state.turn_number:
        return []

    def _apply_play(s: GameState) -> int:
        play_from_hand_pending(s, player, KRCG_ID)
        bring_turn_card_into_play(s, player, krcg_id=KRCG_ID, name=NAME)
        s.players[player].card_played_turn[KRCG_ID] = s.turn_number
        return 1

    return [
        HookOption(
            choice=Choice("loup:play", "Play Loup: put it in play, Toreador get +1 stealth"),
            apply=_apply_play,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_loup_burn(state: GameState, context: Mapping[str, Any]) -> None:
    vampire: VampireInPlay = context["vampire"]
    if vampire.card.clan != CLAN_REQUIREMENT:
        return
    for card in active_turn_cards(state, context["actor_player"], KRCG_ID):
        burn_turn_card(card)


hooks.register(STEALTH_MODIFIER_HOOK, _provide_loup)
hooks.register(ACTION_SUCCEEDED_HOOK, _provide_loup_burn)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.STEALTH_MODIFIER, Hook.ACTION_SUCCEEDED),
        source=__name__,
    )
)
