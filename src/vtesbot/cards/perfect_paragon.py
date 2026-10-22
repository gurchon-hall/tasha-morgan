"""Perfect Paragon (Action Modifier). krcg id 101387.

Card text (verbatim, via krcg, matching `data/cards/101387.json`):
    "[pre] Only usable during the polling step of a political action. This
    vampire gets +3 votes.
    [PRE] Allies and younger vampires get -1 intercept."

Rulings (verbatim, via krcg):
    - "[pre] Cannot be used during a referendum that is automatically
      passing." [PIB 20150105] [LSJ 19980107]
    - "[PRE] Can be played any time during the action before resolution; a
      block attempt is not required." [LSJ 20020612]

`discipline_requirement.disciplines == ["pre"]`; `cost == {"type": "Blood",
"value": 1}`, paid from the playing vampire's own blood, immediately inside
each clause's `apply()` -- an Action Modifier has no block-attempt window
of its own to defer payment to (same timing as `slam.py`'s 1-blood cost).

Status: implemented. Previously `blocked` on ENG-021/RUL-009 (both resolved),
which built `engine/action.py::INTERCEPT_DECREASE_HOOK` for the superior
clause; the basic clause uses the pre-existing
`engine/politics.py::POLLING_STEP_HOOK`.

Basic clause ("This vampire gets +3 votes"): per the Rulebook glossary's
Action Modifier definition ("a card the acting minion can play"), only the
referendum's own *caller* vampire can play it for the bonus -- never any
other ready vampire, and never the non-calling Methuselah's polling-step
window. Appends a `pending["extra_sources"]` descriptor (`politics.py`'s
documented `POLLING_STEP_HOOK` shape); `_collect_vote_sources` turns it into
an ordinary, optional vote source. The "automatically passing" ruling names
a referendum state `resolve_referendum` has no code path for (no card in
this pool causes it) -- unreachable today, not a dropped ruling.

Superior clause ("Allies and younger vampires get -1 intercept"): not
polling-step-gated -- a generic Action Modifier matching its own "any time
before resolution" ruling. Built against `INTERCEPT_DECREASE_HOOK`, offered
to the vampire performing the modified action (`context["acting_vampire"]`)
at both of that hook's offer points (ENG-021/RUL-009). "Younger" uses the
`enchant_kindred.py`/ENG-011 convention: strictly lower printed `capacity`
than the acting vampire. "Allies" is currently vacuous: `attempt_block`'s
candidate pool is built only from `PlayerState.vampires`, never
`PlayerState.allies` (`engine/allies.py`: allies cannot block) -- same
"unreachable today" status as the automatically-passing ruling above.

Double-spend self-gating across the hook's two offer points (RUL-009): no
separate "used" flag is needed -- `apply()`'s `play_from_hand` actually
removes the one physical card from hand, and both providers re-check hand
membership fresh on every `offer()` call, so a card played at one point is
structurally gone by the time the other point is reached.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    INTERCEPT_DECREASE_HOOK,
    PENDING_INTERCEPT_DECREASE_KEY,
    ActiveInterceptDecrease,
)
from vtesbot.engine.attachments import effective_disciplines
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.politics import POLLING_STEP_HOOK
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101387
BASIC = "pre"
SUPERIOR = "PRE"
BLOOD_COST = 1
"""Printed blood-cost box (module docstring): paid immediately, inside each
clause's own `apply()`, independent of which clause is used."""
BASIC_VOTES = 3
SUPERIOR_INTERCEPT_DELTA = -1
CARD_TYPE = "Action Modifier"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own title "Perfect Paragon (Action Modifier)" above."""


def _caller_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    """The referendum's own calling vampire, or `None` if this offer isn't
    to the caller (module docstring) or lacks that context (`.get`, not
    `[]`: some `POLLING_STEP_HOOK` offers carry neither key)."""
    if context.get("player") != context.get("caller"):
        return None
    caller_vampire_id = context.get("caller_vampire_id")
    if caller_vampire_id is None:
        return None
    return state.players[context["player"]].vampires.get(caller_vampire_id)


def _provide_perfect_paragon_basic(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """Basic clause: +3 votes. See module docstring for the caller-only
    gate and the `pending["extra_sources"]` shape."""
    acting_vampire = _caller_vampire(state, context)
    if acting_vampire is None:
        return []
    disciplines = effective_disciplines(state, acting_vampire)
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    player = context["player"]
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if acting_vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    pending = context.get("pending")
    if pending is None:
        return []  # no scratch container to record the vote source into.

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        acting_vampire.blood -= BLOOD_COST
        pending["extra_sources"].append(
            {
                "source_id": f"perfect_paragon:{acting_vampire.instance_id}",
                "player": player,
                "votes": BASIC_VOTES,
                "label": f"Perfect Paragon [pre] ({acting_vampire.card.name})",
            }
        )

    return [
        HookOption(
            choice=Choice(
                "perfect_paragon:basic", "Perfect Paragon [pre]: this vampire gets +3 votes"
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _acting_vampire_for_intercept_decrease(
    state: GameState, context: Mapping[str, Any]
) -> VampireInPlay | None:
    """The vampire performing the modified action -- `INTERCEPT_DECREASE_
    HOOK` is only ever offered to its own controller, so only this one
    vampire is ever checked."""
    acting_vampire_id = context.get("acting_vampire")
    if acting_vampire_id is None:
        return None
    return state.players[context["player"]].vampires.get(acting_vampire_id)


def _provide_perfect_paragon_superior(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """Superior clause: allies and younger vampires get -1 intercept. See
    module docstring for the "younger" convention and the vacuous
    "Allies" half."""
    acting_vampire = _acting_vampire_for_intercept_decrease(state, context)
    if acting_vampire is None:
        return []
    if SUPERIOR not in effective_disciplines(state, acting_vampire):
        return []
    player = context["player"]
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if acting_vampire.blood < BLOOD_COST:
        return []  # printed blood cost: must have enough blood to play at all.
    pending = context.get("pending")
    if pending is None:
        return []  # no scratch container to record the persistent modifier into.
    younger_than_capacity = acting_vampire.card.capacity

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        acting_vampire.blood -= BLOOD_COST
        modifiers = pending.setdefault(PENDING_INTERCEPT_DECREASE_KEY, [])
        modifiers.append(
            ActiveInterceptDecrease(
                delta=SUPERIOR_INTERCEPT_DELTA,
                qualifies=lambda v: v.card.capacity < younger_than_capacity,
            )
        )

    return [
        HookOption(
            choice=Choice(
                "perfect_paragon:superior",
                "Perfect Paragon [PRE]: allies and younger vampires get -1 intercept",
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(POLLING_STEP_HOOK, _provide_perfect_paragon_basic)
hooks.register(INTERCEPT_DECREASE_HOOK, _provide_perfect_paragon_superior)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Perfect Paragon",
        status=Status.IMPLEMENTED,
        hooks=(Hook.POLLING_STEP, Hook.INTERCEPT_DECREASE),
        source=__name__,
    )
)
