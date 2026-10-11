"""Oxford University, England (Master). krcg id 101341.

Card text (verbatim via `krcg.load()[101341].card_text`, re-confirmed live
2026-10-11, matching the text already quoted throughout OQ-23's own
engine-side pass, `docs/OPEN_QUESTIONS.md`, and the raw snapshot saved to
`data/cards/101341.json` per the `implement-card` skill):
    "Unique location.
    You can lock this card and burn X pool during the polling step of a
    political action to get +2X votes."

Rulings: none on file -- `krcg.load()[101341].rulings == []`.

Card type: Master (`types == ["Master"]`). `clans == ["Brujah"]`,
`disciplines == []`, `pool_cost is None` (free to play -- no pool cost to
pay on top of the clan requirement below). Not printed "Trifle.", so
playing it does not grant a bonus master phase action.

Clan requirement (Rulebook SS2 Card Types > "Requirements for Playing
Cards", quoted verbatim, re-fetched 2026-10-11, matching the local cache
`data/sources/rulebook/2026-10-09/2-card-types.md`): "Each library card has
symbols on the attribute bar ... for the card type (except for master
cards), the clan, or Discipline (if any) required to play the card ...
Only a minion who meets the requirements given on a minion card can play
it, whereas only a Methuselah who controls a ready minion who meets the
requirements of a master card can play it." Oxford's own printed clan
symbol is Brujah (`clans == ["Brujah"]`, confirmed live via krcg) -- unlike
a *minion* card's own clan requirement (checked against the specific
*acting* minion, e.g. `forty_seventh_street_royals.py`'s own
`_provide_recruit`), a *master* card's requirement is checked against "a
ready minion" the player merely controls, with no acting-minion concept at
all in the generic Master Phase rule (`engine/phases/master.py`'s own
module docstring: its hook context carries only `player`, never a specific
vampire). So the gate here (`_controls_a_ready_brujah`) is "does `player`
control at least one ready Brujah vampire right now", not tied to any one
specific vampire -- and it governs only the initial play of the card (a
one-time playability check, Rulebook SS2's own "Requirements for Playing
Cards" heading); Oxford's own repeatable polling-step ability below carries
no further clan-conditional clause of its own, so no analogous check is
made there.

Two independent clauses:

1. "Unique location." -- a standalone Master card, not an attachment
   (`engine/state.py::MasterCardInPlay`, OQ-23 `docs/OPEN_QUESTIONS.md`,
   resolved and independently `rules-auditor`-reviewed clean): wired
   against the `"master_phase_play"` hook exactly like Life in the City
   (`engine/phases/master.py`), via `bring_master_card_into_play` then
   (since this card is printed "Unique") `detect_contest_on_bring_into_
   play` -- mirrors `tests/rules/test_master_cards.py::
   test_master_phase_play_end_to_end_brings_a_card_into_play_and_detects_
   contest`'s own proven production-call-site shape, now with a real card
   instead of a fake stand-in provider. Not a trifle (`apply` returns
   `False`).
2. "You can lock this card and burn X pool during the polling step of a
   political action to get +2X votes." -- wired against the
   `"polling_step"` hook (`engine/politics.py::POLLING_STEP_HOOK`), built on
   `variable_pool_burn_vote_options` (OQ-23's own reusable primitive for
   exactly this "burn X pool for Y*X votes" shape; `votes_per_pool=2` per
   the printed "+2X votes"), with `on_burn` locking this specific
   `MasterCardInPlay` instance as the ability's own additional cost ("lock
   this card *and* burn X pool"). Offered only:
     (a) while this hook fires at all -- `POLLING_STEP_HOOK` is only ever
         dispatched from `engine/politics.py::resolve_referendum`'s
         pre-cast window, itself only reached during an unblocked political
         action's polling step (`engine/politics.py::political_action`), so
         "during the polling step of a political action" is already
         satisfied by registering against this hook, with no further
         action-type check needed here -- mirrors every other
         `POLLING_STEP_HOOK` provider's own scope;
     (b) for this specific instance's own controller only ("you can lock
         this card" -- Oxford is its controller's own political resource,
         not a shared one): `_provide_oxford_polling_step` only ever
         inspects `state.players[context["player"]].master_cards`, which by
         construction can never contain the opponent's own copy; and
     (c) only while this instance is `zone == "in_play"` and `locked is
         False` (`MasterCardInPlay.is_unlocked_in_play`) -- a contested or
         burned copy is out of play and cannot react, and an already-locked
         copy (e.g. already used once this same polling step, or simply not
         yet unlocked since an earlier use) must not be offered the ability
         again until its own next unlock phase (`engine/phases/unlock.py::
         _unlock_own_master_cards`) -- mirrors `tests/rules/
         test_politics.py::
         test_an_already_locked_location_is_not_offered_the_option_again`'s
         own fake-provider shape exactly.

Status: IMPLEMENTED. Was `blocked` with a stale `blocked_reason="OQ-6"`
(OQ-6 itself long resolved); the actual remaining blocker, OQ-23's missing
standalone master-card entity, is now resolved and independently
`rules-auditor`-reviewed clean, per this pass's own task. `Hook.
LOCATION_ENTITY` is no longer cited here: OQ-23's own resolution found
"location" is not a distinct krcg card type at all (free text on an
ordinary Master card), so this card needs no entity beyond the now-generic
`MasterCardInPlay` -- `Hook.LOCATION_ENTITY` itself is left unchanged in
`cards/registry.py`, since 17 other "Unique location."/standalone-Master-
card hits from OQ-23's own sweep are still unimplemented and may still find
it a reasonable classification tag until they are built.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.master_cards import (
    bring_master_card_into_play,
    detect_contest_on_bring_into_play,
)
from vtesbot.engine.politics import POLLING_STEP_HOOK, variable_pool_burn_vote_options
from vtesbot.engine.state import GameState, MasterCardInPlay

KRCG_ID = 101341
NAME = "Oxford University, England"
MASTER_PHASE_PLAY_HOOK = "master_phase_play"
CLAN_REQUIREMENT = ("Brujah",)
VOTES_PER_POOL = 2


def _controls_a_ready_brujah(state: GameState, player: str) -> bool:
    """Rulebook SS2 Card Types > "Requirements for Playing Cards" (module
    docstring): "only a Methuselah who controls a ready minion who meets
    the requirements of a master card can play it" -- not tied to any one
    specific vampire, unlike a minion card's own acting-minion-scoped
    requirement."""
    return any(
        vampire.zone == "ready" and vampire.card.clan in CLAN_REQUIREMENT
        for vampire in state.players[player].vampires.values()
    )


def _provide_oxford_master_phase_play(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if not _controls_a_ready_brujah(state, player):
        return []

    def _apply(s: GameState) -> bool:
        play_from_hand(s, player, KRCG_ID)
        card = bring_master_card_into_play(s, player, krcg_id=KRCG_ID, name=NAME)
        detect_contest_on_bring_into_play(s, card)
        return False  # not a trifle: no extra master phase action.

    return [
        HookOption(
            choice=Choice("oxford_university_england", f"Play {NAME}"),
            apply=_apply,
        )
    ]


def _own_unlocked_in_play_instances(state: GameState, player: str) -> list[MasterCardInPlay]:
    return [
        card
        for card in state.players[player].master_cards.values()
        if card.krcg_id == KRCG_ID and card.is_unlocked_in_play
    ]


def _provide_oxford_polling_step(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    if context.get("phase") != "before_cast":
        return []
    player = context["player"]
    pending = context["pending"]

    options: list[HookOption] = []
    for card in _own_unlocked_in_play_instances(state, player):

        def _lock(s: GameState, card: MasterCardInPlay = card) -> None:
            card.locked = True

        options.extend(
            variable_pool_burn_vote_options(
                state,
                player,
                source_id_prefix=f"oxford:{card.instance_id}",
                label=NAME,
                votes_per_pool=VOTES_PER_POOL,
                pending=pending,
                on_burn=_lock,
            )
        )
    return options


hooks.register(MASTER_PHASE_PLAY_HOOK, _provide_oxford_master_phase_play)
hooks.register(POLLING_STEP_HOOK, _provide_oxford_polling_step)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.MASTER_PHASE_PLAY, Hook.POLLING_STEP),
        source=__name__,
    )
)
