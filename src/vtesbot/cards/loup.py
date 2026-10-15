"""Loup (Action Modifier). krcg id 102273.

Card text (verbatim, via the installed `krcg` package's
`krcg.vtes.VTES['Loup'].card_text`, re-verified live 2026-10-14, matching
the raw snapshot `data/cards/102273.json`): "Only one Loup can be played
each turn.\nPut this card in play. Toreador get +1 stealth. Burn this card
at the end of the turn or after a Toreador performs a successful action."
Clan Toreador (`clans == ["Toreador"]`); no discipline requirement, no cost.

Rulings:
    - "Can be used even if the stealth is not currently needed."
      [LSJ 20011214-2].
    - OQ-40 (`docs/OPEN_QUESTIONS.md`, resolved -- ruling via a trusted VEKN
      judge on the international rulings forum, pending official
      publication; posed scenario: a Loup in play with its controller's own
      Toreador vampires all failing to act, a second Methuselah's Masika
      (base, G1) with an Enkil Cog about to act): "Yes, [Masika] has +1
      stealth[,] and Loup burns if [the action] succeeds (card text)."
      Confirms the plain, unqualified "Toreador get +1 stealth" (no "you
      control") and the burn trigger ("after a Toreador performs a
      successful action") are both table-wide -- *any* Toreador vampire in
      play benefits from *any* in-play Loup, and *any* Toreador's
      successful action burns *every* in-play Loup, regardless of who
      controls the vampire or the card.

Built on OQ-34's own primitives (`docs/OPEN_QUESTIONS.md`, resolved):
`engine/turn_cards.py` (`TurnCardInPlay`/`bring_turn_card_into_play`/
`burn_turn_card`/`active_turn_cards`) and `engine/action.py::
ACTION_SUCCEEDED_HOOK`. OQ-40's own resolution (above) means neither clause
is scoped to a single controller: `_provide_loup` below checks every
player's own `turn_cards` for an active Loup (not only `context["player"]`'s
own), and `_provide_loup_burn` burns every in-play Loup across every player.
Only *playing* a copy from hand stays controller-bound, by construction --
a Methuselah can only ever play a card from their own hand.

One provider, registered against `STEALTH_INCREASE_HOOK` (`engine/
action.py`, OQ-39, resolved -- see below), does double duty, gated
throughout on the acting vampire (`context["acting_vampire"]`, re-resolved
fresh every call -- same "bind to the specific acting minion" precedent as
`forty_seventh_street_royals.py::_provide_recruit`, OQ-13) being Toreador --
Rulebook §2 "Requirements for Playing Cards": "Only a minion who meets the
requirements given on a minion card can play it". Both halves below are
offered together, not as an either/or branch (OQ-40's table-wide reading
means they are independent, additive opportunities -- e.g. the acting
player may activate the *other* Methuselah's already-in-play Loup *and*
play their own fresh copy from hand, for two separately-tracked grants):
  - one "activate this standing bonus" option per currently in-play Loup
    instance (any controller) not yet granted this action, keyed by that
    instance's own `instance_id` (`LOUP_STEALTH_GRANTED_KEY`, below) -- no
    re-play, no cost (plain passive bonus, same `played_card_type=None`
    reasoning as `maila.py`'s own ability activation -- this option is not
    a card being played);
  - the acting player's own "play a copy from hand" option, additionally
    gated on the "only one Loup can be played each turn" cap
    (`PlayerState.card_played_turn`, `engine/state.py`, mirroring
    `VampireInPlay.ability_used_turn`'s own shape but scoped to the
    controller, since this cap is a plain card-play restriction, not a
    specific minion's ability) -- this stays bound to the acting player's
    own hand regardless of OQ-40, since nothing lets a Methuselah play a
    card from someone else's hand.

Each granted option records a persistent `ActiveStealthIncrease(delta=1)`
into `pending[PENDING_STEALTH_INCREASE_KEY]` rather than returning a
one-shot numeric delta (`STEALTH_INCREASE_HOOK`'s own contract, `engine/
action.py`), capped per Loup *instance* at most once per *action* via
`LOUP_STEALTH_GRANTED_KEY` (a `set[str]` of already-granted `instance_id`s,
not a flat flag -- OQ-40 means more than one distinct Loup, each its own
independent source, can legally be in play across two controllers at once,
and each should be able to contribute its own +1 once, not be collapsed
into a single global cap). Without a per-instance cap at all, offering the
same standing "+1 stealth" repeatedly across this hook's own two offer
points (proactive and reactive, within one action) would let any one
instance stack indefinitely, which the printed text's plain, singular
"+1 stealth" does not support (a `rules-auditor`-style finding made while
migrating off the old `STEALTH_MODIFIER_HOOK`-only wiring below, which had
no such cap and could have been exploited the same way, though no
registered test ever did).

OQ-39 (`docs/OPEN_QUESTIONS.md`, resolved -- previously the known gap this
module shipped `Status.IMPLEMENTED` with): the on-file ruling's full
generality ("even if the stealth is not currently needed") exempts Loup
from the Rulebook's general default stealth-timing rule ("Stealth can be
added during an action only when needed..." -- `data/sources/rulebook/
2026-10-09/4-detailed-turn-sequence.md:559-561`), but the old
`STEALTH_MODIFIER_HOOK` registration was only ever reachable from within
that very "only when needed" ping-pong (`engine/action.py::_duel_stealth_
intercept`), never when no block attempt happens at all, or while stealth
already strictly exceeds intercept pre-modifier. This module now registers
against `STEALTH_INCREASE_HOOK` instead -- `engine/action.py::attempt_block`
offers it to the acting player proactively, at the very top of its retry
loop, before `defender`'s own candidate pool is even computed (mirroring
`INTERCEPT_DECREASE_HOOK`'s own OQ-30 shape) -- so Loup can now be played,
and its ongoing bonus activated, even against a fully unblockable action.
`tests/cards/test_loup.py::
test_can_be_played_proactively_even_when_the_action_is_unblockable` proves
the fix directly.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand_pending
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    ACTION_SUCCEEDED_HOOK,
    PENDING_STEALTH_INCREASE_KEY,
    STEALTH_INCREASE_HOOK,
    ActiveStealthIncrease,
)
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
LOUP_STEALTH_GRANTED_KEY = "loup_stealth_granted"
"""`pending[...]` key (module docstring): a `set[str]` of already-granted
turn-card `instance_id`s, capping each distinct in-play Loup at most once
per action, across both of `STEALTH_INCREASE_HOOK`'s own offer points."""


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
    pending = context.get("pending")
    if pending is None:
        return []  # no scratch container to record the persistent grant into.

    granted: set[str] = pending.setdefault(LOUP_STEALTH_GRANTED_KEY, set())
    options: list[HookOption] = []

    # OQ-40: any in-play Loup, any controller, may be activated for the
    # acting Toreador vampire's own benefit.
    for owner in state.players:
        for card in active_turn_cards(state, owner, KRCG_ID):
            if card.instance_id in granted:
                continue

            def _apply_bonus(s: GameState, instance_id: str = card.instance_id) -> None:
                del s
                pending.setdefault(PENDING_STEALTH_INCREASE_KEY, []).append(
                    ActiveStealthIncrease(delta=1)
                )
                granted.add(instance_id)

            options.append(
                HookOption(
                    choice=Choice(
                        f"loup:stealth_bonus:{card.instance_id}",
                        f"Loup ({card.controller}'s copy): Toreador get +1 stealth",
                    ),
                    apply=_apply_bonus,
                )
            )

    if any(card.krcg_id == KRCG_ID for card in state.players[player].hand) and (
        state.players[player].card_played_turn.get(KRCG_ID) != state.turn_number
    ):

        def _apply_play(s: GameState) -> None:
            play_from_hand_pending(s, player, KRCG_ID)
            turn_card = bring_turn_card_into_play(s, player, krcg_id=KRCG_ID, name=NAME)
            s.players[player].card_played_turn[KRCG_ID] = s.turn_number
            pending.setdefault(PENDING_STEALTH_INCREASE_KEY, []).append(
                ActiveStealthIncrease(delta=1)
            )
            granted.add(turn_card.instance_id)

        options.append(
            HookOption(
                choice=Choice("loup:play", "Play Loup: put it in play, Toreador get +1 stealth"),
                apply=_apply_play,
                played_card_type=CARD_TYPE,
            )
        )

    return options


def _provide_loup_burn(state: GameState, context: Mapping[str, Any]) -> None:
    vampire: VampireInPlay = context["vampire"]
    if vampire.card.clan != CLAN_REQUIREMENT:
        return
    # OQ-40: any Toreador's successful action burns every in-play Loup,
    # regardless of who controls the card or the acting vampire.
    for owner in state.players:
        for card in active_turn_cards(state, owner, KRCG_ID):
            burn_turn_card(card)


hooks.register(STEALTH_INCREASE_HOOK, _provide_loup)
hooks.register(ACTION_SUCCEEDED_HOOK, _provide_loup_burn)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.STEALTH_INCREASE, Hook.ACTION_SUCCEEDED),
        source=__name__,
    )
)
