"""Weighted Walking Stick (Combat). krcg id 102169.

Card text (verbatim, via the installed `krcg` 4.18 `krcg.vtes.VTES` package
-- the project's `uv run` virtualenv has a newer `krcg` (5.14) whose own
`krcg.load()` API has no `to_json()`/raw-schema equivalent, the same
pre-existing gap `organized_resistance.py`'s own docstring notes --
2026-10-14, matching the raw snapshot saved to `data/cards/102169.json`):
    "Only usable before range is determined during the first round.
    Put this card with 5 counters on it on this minion; it becomes a
    melee weapon equipment that can strike: strength+1 damage. For each
    damage inflicted by this strike (even if prevented), burn 1 counter
    from this card. Burn this card if it has no counters. A minion can
    have only one Weighted Walking Stick."

Rulings (verbatim, via krcg; `VTES["Weighted Walking Stick"].rulings`):
    - "If the damage is reduced (eg. {Nephandus}) or not inflicted (eg.
      {Blood Fury}), the corresponding token is not burned (contrary to
      prevented damage)." [LSJ 20100519]
    - "Full damage is applied if there are any counter left, even just
      1." [ANK 20201229-2]

Card type: Combat (`types == ["Combat"]`). `clans == []`,
`disciplines == []` -- no clan/Discipline requirement; the only
playability gate is the printed "Only usable before range is determined
during the first round" timing restriction. `blood_cost`/`pool_cost` are
both `None` (free). Legal since 2002-09-18; confirmed on the active 2P
allowed list (`data/formats/2p/2026-10-03.json`) and in
`data/decks/vekn-2p/toreador.json`.

Status: implemented (OQ-47, `docs/OPEN_QUESTIONS.md`, resolved). Attach
clause rides `engine/combat.py::BEFORE_RANGE_HOOK` (offered to both
combatants' controllers once, round 1 only); "this minion" is read as the
playing controller's own combatant in the fight (the general equipment
convention -- a player attaches to a minion they control, never the
opponent's). "A minion can have only one Weighted Walking Stick": the
attach option is simply not offered once `vampire.attachments` already
carries a `krcg_id == KRCG_ID` entry. "it becomes a melee weapon
equipment": `attach_card`'s own `is_equipment=True` (Rulebook §2 Card
Types "Equipment cards"), the printed-card-type fact `engine/diablerie.py
::resolve_diablerie` step 2 ("the diablerist may take any equipment on
the victim") gates on.

Strike clause rides `COMBAT_STRIKE_OPTION_HOOK` with no change to its
existing provider contract (pre-prevention, post-reduction damage, per
that hook's own docstring and `engine/combat.py`'s "Before Range" section)
-- `_apply` computes `strength+1` the same non-hardcoded way `cards/
slam.py`/`cards/dust_up.py` do (base hand-strike strength plus any live
`combat_strength_modifier`), burns `min(amount, counters)` off the
attachment and removes it once empty, then returns the *full* `amount`
unreduced: "[f]ull damage is applied if there are any counter left, even
just 1" [ANK 20201229-2] is thereby a direct consequence of returning the
full amount regardless of how many counters are actually burned, not a
separate branch. "For each damage inflicted ... even if prevented":
counters are burned here, inside `apply`, strictly before whatever
prevention/mend step the engine's own damage pipeline runs downstream on
the returned amount -- so a later prevention never claws back a burned
counter. [LSJ 20100519]'s "reduced or not inflicted" half (Nephandus,
Blood Fury) has no reachable case: neither card, nor any generic
"reduce/skip this specific strike" mechanism, is implemented in this
project, mirroring `cards/slam.py`'s own "Hidden Lurker" citation (an
on-file ruling for an interaction with an unimplemented card, vacuously
satisfied).

Not enforced: the general Rulebook §4 "Resolve Strike" rule that a melee
(non-ranged, non-"R") strike is "effective only at close range" -- no
range-gating mechanism exists for *any* melee strike yet, including the
engine's own built-in hand strike (`engine/combat.py` module docstring,
"Range-gating ... is explicitly not built this pass"); a pre-existing,
engine-wide, documented scope limitation, not specific to this card.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.combat import (
    BEFORE_RANGE_HOOK,
    COMBAT_STRENGTH_MODIFIER_HOOK,
    COMBAT_STRIKE_OPTION_HOOK,
    HAND_STRIKE_STRENGTH,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 102169
NAME = "Weighted Walking Stick"
INITIAL_COUNTERS = 5
"""Verbatim "with 5 counters on it"."""
STRIKE_BONUS = 1
"""Verbatim "strength+1 damage"."""
CARD_TYPE = "Combat"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Combat" docstring fact above -- set only on
the attach option (the actual card play event); the strike option merely
claims an effect an already-played, already-attached card grants, exactly
like `cards/dust_up.py`'s own claimed-additional-strike option, so it
leaves `played_card_type` at its default `None` (that field's own
docstring)."""


def _own_vampire_id(context: Mapping[str, Any]) -> str:
    """ "This minion" (the attach target) is the playing controller's own
    combatant in the fight -- never the opponent's (module docstring)."""
    if context["player"] == context["acting_player"]:
        return context["acting_vampire"]
    return context["blocking_vampire"]


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _find_attachment(vampire: VampireInPlay) -> CardAttachment | None:
    return next((a for a in vampire.attachments if a.krcg_id == KRCG_ID), None)


def _provide_attach(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "Put this card with 5 counters on it on this minion ..." -- see
    module docstring for "this minion"'s reading and the one-per-minion
    cap."""
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    vampire = state.players[player].vampires[_own_vampire_id(context)]
    if _find_attachment(vampire) is not None:
        return []  # "A minion can have only one Weighted Walking Stick."

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        attach_card(
            s,
            vampire,
            controller=player,
            krcg_id=KRCG_ID,
            name=NAME,
            counters=INITIAL_COUNTERS,
            is_equipment=True,
        )

    return [
        HookOption(
            choice=Choice(
                f"weighted_walking_stick:attach:{vampire.instance_id}",
                f"Weighted Walking Stick: attach to {vampire.card.name}",
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_strike(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "... it becomes a melee weapon equipment that can strike:
    strength+1 damage. For each damage inflicted by this strike (even if
    prevented), burn 1 counter from this card. Burn this card if it has no
    counters." -- see module docstring for the counter-burn/full-damage
    mechanics."""
    player = context["player"]
    vampire = state.players[player].vampires.get(context["vampire"])
    if vampire is None:
        return []
    wws = _find_attachment(vampire)
    if wws is None or (wws.counters or 0) <= 0:
        return []
    base = HAND_STRIKE_STRENGTH + hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK,
        state,
        player=player,
        vampire=context["vampire"],
        opponent=context["opponent"],
    )
    amount = base + STRIKE_BONUS

    def _apply(s: GameState) -> int:
        counters = wws.counters or 0
        wws.counters = counters - min(amount, counters)
        if wws.counters == 0:
            vampire.attachments.remove(wws)
        return amount

    return [
        HookOption(
            choice=Choice(
                f"weighted_walking_stick:strike:{vampire.instance_id}",
                "Weighted Walking Stick: strike",
            ),
            apply=_apply,
        )
    ]


hooks.register(BEFORE_RANGE_HOOK, _provide_attach)
hooks.register(COMBAT_STRIKE_OPTION_HOOK, _provide_strike)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.BEFORE_RANGE, Hook.COMBAT_STRIKE_OPTION),
        source=__name__,
    )
)
