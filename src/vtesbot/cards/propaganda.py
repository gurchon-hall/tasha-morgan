"""Propaganda (Action). krcg id 101495.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-16, matching the raw
snapshot saved to `data/cards/101495.json`):
    "[pre] Ⓓ Bleed with +1 bleed. Titled vampires cannot block this
    action.
    [PRE] As above, and the target Methuselah locks a ready unlocked
    minion they control."

Rulings: none on file (`rulings == []`).

Card type: Action (`types == ["Action"]`). `discipline_requirement ==
{"type": "Mono", "disciplines": ["pre"]}`; `clan_requirement == []`;
`cost == {"type": "Blood", "value": 2}` (burned by the acting vampire,
only on the unblocked branch -- Rulebook §4 step 3, "If blocked ->
action card burned, cost not paid", `dominate_kine.py`'s own
convention). Legal since 1996-11-27; on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`). Both clauses carry "Ⓓ": collapses
to the single 2P opponent (CLAUDE.md §3), not RUL-001.

Status: implemented, against two primitives built this session: `engine/
action.py::attempt_block`/`perform_minion_action`'s `block_candidate_
predicate` parameter (an unconditional, property-based block-candidate
filter, re-evaluated fresh on every retry -- "titled vampires cannot
block this action" for both clauses, `lambda v: v.card.title is None`)
and `engine/action.py::force_lock_ready_unlocked_minion` (the superior
clause's "the target Methuselah locks a ready unlocked minion they
control"; per that function's own docstring, the *target* Methuselah --
the defender -- chooses which of their own vampires to lock, sourced
from Brujah Debate's identical "[that Methuselah] locks a [vampire] they
control" ruling).

Bleed amount (both clauses): default (1) + this card's own printed "+1
bleed" = 2, baked into the baseline the same way `enchant_kindred.py`/
`dominate_kine.py` do -- composable with any other bleed-amount hook
since `ActionCardSpec.action=ACTION_BLEED` is set (ENG-011 follow-up
requirement).

Superior clause's forced lock happens only on the unblocked resolution
(part of `resolve()`, after the bleed itself resolves); if the defender
has no ready unlocked vampire at all, `force_lock_ready_unlocked_minion`
fizzles with no decision raised ("cannot do the impossible" convention)
-- the bleed itself still goes through regardless.

ENG-037: both clauses call `remove_from_hand`
(not `play_from_hand`) and set `ActionCardSpec.name=NAME`, so `engine/
phases/minion.py::_perform_action_card` can interleave a future Reflex
card's own cancel-as-played window before drawing the replacement
(Finding 1), and so a second physical copy is not offered once either
clause has already been played this turn (Finding 2, keyed by `NAME` --
both clauses are the same physical card).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import remove_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_BLEED, force_lock_ready_unlocked_minion
from vtesbot.engine.attachments import effective_disciplines
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
    BLEED_AMOUNT_MODIFIER_HOOK,
    PENDING_BLEED_AMOUNT_KEY,
    ActionCardSpec,
    action_card_already_played_this_turn,
)
from vtesbot.engine.pool import lose_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101495
NAME = "Propaganda"
"""`ActionCardSpec.name`/`CardRegistration.name` (ENG-037): the generic "same
named action card at most once per turn" cap is keyed by this exact string for
both clauses -- they are the same physical card."""
BASIC = "pre"
SUPERIOR = "PRE"
BLEED_BASE_AMOUNT = 2
"""Default bleed amount (1) + this card's own printed "+1 bleed", baked into
the baseline the same way `enchant_kindred.py`/`dominate_kine.py` do -- not a
separately-offered, declinable modifier."""
BLOOD_COST = 2
"""Printed blood-cost box: burned from the acting vampire, only on the
unblocked branch (module docstring)."""
CARD_TYPE = "Action"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Action" docstring fact above."""


def _not_titled(vampire: VampireInPlay) -> bool:
    """ "Titled vampires cannot block this action." (both clauses)."""
    return vampire.card.title is None


def _controllers_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    return state.players[context["player"]].vampires.get(context["vampire"])


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _provide_propaganda_basic(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[pre] Ⓓ Bleed with +1 bleed. Titled vampires cannot block this
    action." """
    player = context["player"]
    acting_vampire = _controllers_vampire(state, context)
    if acting_vampire is None:
        return []
    disciplines = effective_disciplines(state, acting_vampire)
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []
    if acting_vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    if action_card_already_played_this_turn(state, acting_vampire, NAME):
        return []  # ENG-037 Finding 2: same named action card, once per turn.

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            other = s.other_player(player)
            acting_vampire.blood -= BLOOD_COST  # paid now: action resolved unblocked.
            base_amount = (
                BLEED_BASE_AMOUNT
                + hooks.sum_modifiers(
                    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
                    s,
                    player=player,
                    vampire=acting_vampire.instance_id,
                )
                + pending.get(PENDING_BLEED_AMOUNT_KEY, 0)
            )
            amount_box = [base_amount]
            hooks.resolve_impulse_window(
                s,
                BLEED_AMOUNT_MODIFIER_HOOK,
                player,
                other,
                context={
                    "vampire": acting_vampire.instance_id,
                    "amount": amount_box,
                    "pending": pending,
                },
            )
            amount = max(0, amount_box[0])
            lose_pool(s, other, amount)
            if amount >= 1:
                s.edge_holder = player

        return ActionCardSpec(
            base_stealth=0,
            directed=True,
            resolve=resolve,
            action=ACTION_BLEED,
            block_candidate_predicate=_not_titled,
            name=NAME,
        )

    return [
        HookOption(
            choice=Choice(
                "propaganda:basic",
                "Propaganda [pre]: Bleed with +1 bleed; titled vampires cannot block",
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_propaganda_superior(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[PRE] As above, and the target Methuselah locks a ready unlocked
    minion they control." """
    player = context["player"]
    acting_vampire = _controllers_vampire(state, context)
    if acting_vampire is None:
        return []
    if SUPERIOR not in effective_disciplines(state, acting_vampire):
        return []
    if not _has_card_in_hand(state, player):
        return []
    if acting_vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    if action_card_already_played_this_turn(state, acting_vampire, NAME):
        return []  # ENG-037 Finding 2: same named action card, once per turn.

    def _apply(s: GameState) -> ActionCardSpec:
        remove_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            other = s.other_player(player)
            acting_vampire.blood -= BLOOD_COST  # paid now: action resolved unblocked.
            base_amount = (
                BLEED_BASE_AMOUNT
                + hooks.sum_modifiers(
                    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
                    s,
                    player=player,
                    vampire=acting_vampire.instance_id,
                )
                + pending.get(PENDING_BLEED_AMOUNT_KEY, 0)
            )
            amount_box = [base_amount]
            hooks.resolve_impulse_window(
                s,
                BLEED_AMOUNT_MODIFIER_HOOK,
                player,
                other,
                context={
                    "vampire": acting_vampire.instance_id,
                    "amount": amount_box,
                    "pending": pending,
                },
            )
            amount = max(0, amount_box[0])
            lose_pool(s, other, amount)
            if amount >= 1:
                s.edge_holder = player
            # "the target Methuselah locks a ready unlocked minion they
            # control": fizzles with no decision raised if `other` has none
            # at all (force_lock_ready_unlocked_minion's own "cannot do the
            # impossible" convention) -- the bleed itself still went through
            # above, regardless of this clause's own outcome.
            force_lock_ready_unlocked_minion(s, other, reason="propaganda_superior")

        return ActionCardSpec(
            base_stealth=0,
            directed=True,
            resolve=resolve,
            action=ACTION_BLEED,
            block_candidate_predicate=_not_titled,
            name=NAME,
        )

    return [
        HookOption(
            choice=Choice(
                "propaganda:superior",
                "Propaganda [PRE]: Bleed with +1 bleed; titled vampires cannot block; "
                "target Methuselah locks a ready unlocked minion",
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_propaganda_basic)
hooks.register(ACTION_CARD_PLAY_HOOK, _provide_propaganda_superior)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
