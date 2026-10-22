"""Spirit's Touch (Reaction). krcg id 101850.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-18, matching the raw
snapshot saved to `data/cards/101850.json`):
    "[aus] +1 intercept.
    [AUS] As above, with 1 optional maneuver during the resulting combat
    if this vampire blocks."

Rulings (verbatim, via krcg; `cards["Spirit's Touch"].rulings`):
    - "[AUS] The maneuver can only be used if the block is successful, and
      only in the resulting (block-induced) combat. It does not carry over
      to a follow-up combat (eg. {Psyche!})." [LSJ 20010813]
      [LSJ 20010819-2]
    - "[AUS] The maneuver is provided again if a second block happens on
      the same action (eg. after {Form of Mist})." [LSJ 20010814-2]

Card type: Reaction (`types == ["Reaction"]`). `discipline_requirement ==
{"type": "Mono", "disciplines": ["aus"]}` -- basic Auspex for the `[aus]`
clause, superior for `[AUS]`. `clan_requirement == []`, `cost is None`
(ordinary Reaction, no printed play cost). Legal since 1994-09-15;
confirmed on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`) and in the suggested 2P decklist `data/decks/vekn-2p/
salubri.json` (1 copy, listed under VEKN's own typo'd name "Spirit's
Thouch, The" -- see that entry's own `note`, not corrected here).

Status: implemented. Structurally identical to `cards/precognition.py`'s
own two clauses, same physical-card shape as `cards/eyes_of_argus.py`:

"[aus] +1 intercept.": an unqualified `INTERCEPT_MODIFIER_HOOK` bonus to
whichever block attempt is in progress, same reading as `precognition.py`'s
own basic clause -- offered to any of the defender's own ready, unlocked
Auspex vampires, not already used this action (shared `USED_BY_KEY` cap,
§8 glossary).

"[AUS] As above, with 1 optional maneuver during the resulting combat if
this vampire blocks.": superior Auspex vampires are additionally offered a
second option for the *same* physical card (Rulebook §3). Its own `apply`
plays the card and records a block-time combat grant for *this specific
vampire* via `grant_block_time_combat_effect`, forwarded by `perform_
minion_action` into the resulting `run_combat` call only if this exact
vampire ends up the successful blocker [LSJ 20010813]. Unlike Precognition's
own round-1-only damage prevention, this card prints no round restriction
("during the resulting combat", not "during the first round"), so the
`MANEUVER_HOOK` provider below gates only on `block_time_combat_grant_
available`, offered on every Determine Range turn of that combat until
consumed -- `BLOCK_TIME_COMBAT_GRANT_KEY` lives on `combat_state`, which
persists for the whole combat, not per-round. "Only in the resulting
(block-induced) combat. It does not carry over to a follow-up combat"
[LSJ 20010819-2] needs no extra code: `perform_minion_action` forwards the
grant into exactly one `run_combat` call (the one for the successful
blocker); any later, separate combat (e.g. triggered by Psyche!) is a
distinct `run_combat` invocation with its own fresh `combat_state`, which
never receives this grant.

"The maneuver is provided again if a second block happens on the same
action (eg. after Form of Mist)" [LSJ 20010814-2]: no special-case code,
same reasoning as `precognition.py`'s own docstring for the identical
ruling on its sibling card -- nothing here marks the physical card as
permanently spent beyond the standard "no card is played twice per action
by the same vampire" cap (`USED_BY_KEY`); a second, separate block attempt
within the same action that re-reaches the stealth/intercept ping-pong
would simply let this same provider offer and record a fresh grant again.
Not reachable by any mechanism implemented in this project today (no
Form-of-Mist-like "dissolved blocker triggers a new attempt" effect), so
not exercised by a scenario test, same latitude `precognition.py`'s own
test file takes.

Eligibility mirrors `precognition.py`'s own `_eligible` shape: `player`'s
own ready, unlocked vampires with `"aus"` or `"AUS"` in `card.disciplines`
(plain printed stat, not attachment-aware `effective_disciplines` -- ENG-002
noted, not acted on here, matching every other discipline-gated card in
this project).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import INTERCEPT_MODIFIER_HOOK, grant_block_time_combat_effect
from vtesbot.engine.combat import (
    MANEUVER_HOOK,
    block_time_combat_grant_available,
    consume_block_time_combat_grant,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101850
NAME = "Spirit's Touch"
BASIC = "aus"
SUPERIOR = "AUS"
INTERCEPT_BONUS = 1
"""Verbatim "+1 intercept."."""
GRANT_NAME = "spirits_touch_block_maneuver"
"""`engine/combat.py::BLOCK_TIME_COMBAT_GRANT_KEY`'s own per-grant name for
this card's superior clause -- never read by any other card."""
USED_BY_KEY = "spirits_touch_used_by"
"""§8 glossary "A minion cannot play the same reaction card more than once
during a single action" -- shared between both clauses (same physical
card), mirrors `cards/precognition.py`'s own `USED_BY_KEY`."""
CARD_TYPE = "Reaction"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Reaction" docstring fact above. The later
`MANEUVER_HOOK` option (claiming an already-earned grant, not playing a
card) leaves this at its default `None`, mirroring `cards/precognition.py`'s
own `DAMAGE_PREVENTION_HOOK` precedent for a claimed-not-played grant."""


def _used_by(pending: dict[str, Any] | None) -> set[str]:
    if pending is None:
        return set()
    return pending.setdefault(USED_BY_KEY, set())


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _is_auspex(vampire: VampireInPlay) -> bool:
    disciplines = vampire.card.disciplines
    return BASIC in disciplines or SUPERIOR in disciplines


def _eligible(state: GameState, player: str, used_by: set[str]) -> list[VampireInPlay]:
    return [
        v
        for v in state.players[player].vampires.values()
        if v.is_ready_unlocked and v.instance_id not in used_by and _is_auspex(v)
    ]


def _provide_spirits_touch_intercept(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[aus] +1 intercept." and "[AUS] As above, with 1 optional
    maneuver during the resulting combat if this vampire blocks." -- see
    module docstring for each clause's own gates."""
    player = context["player"]  # INTERCEPT_MODIFIER_HOOK is only ever offered to the defender.
    if not _has_card_in_hand(state, player):
        return []

    pending = context.get("pending")
    used_by = _used_by(pending)
    eligible = _eligible(state, player, used_by)
    if not eligible:
        return []

    options: list[HookOption] = []
    for vampire in eligible:

        def _make_basic(v: VampireInPlay):
            def _apply(s: GameState) -> int:
                play_from_hand(s, player, KRCG_ID)
                used_by.add(v.instance_id)
                return INTERCEPT_BONUS

            return _apply

        options.append(
            HookOption(
                choice=Choice(
                    f"spirits_touch:basic:{vampire.instance_id}",
                    f"Spirit's Touch [aus]: +{INTERCEPT_BONUS} intercept ({vampire.card.name})",
                ),
                apply=_make_basic(vampire),
                played_card_type=CARD_TYPE,
            )
        )
        if SUPERIOR in vampire.card.disciplines:

            def _make_superior(v: VampireInPlay):
                def _apply(s: GameState) -> int:
                    play_from_hand(s, player, KRCG_ID)
                    used_by.add(v.instance_id)
                    grant_block_time_combat_effect(pending, v.instance_id, GRANT_NAME)
                    return INTERCEPT_BONUS

                return _apply

            options.append(
                HookOption(
                    choice=Choice(
                        f"spirits_touch:superior:{vampire.instance_id}",
                        f"Spirit's Touch [AUS]: +{INTERCEPT_BONUS} intercept, 1 optional "
                        f"maneuver in the resulting combat if they block ({vampire.card.name})",
                    ),
                    apply=_make_superior(vampire),
                    played_card_type=CARD_TYPE,
                )
            )
    return options


def _provide_spirits_touch_maneuver(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """The superior clause's own maneuver half, claimed (not played) once
    the grant it recorded has survived into the resulting combat -- see
    module docstring."""
    del state
    if not block_time_combat_grant_available(context, GRANT_NAME):
        return []

    def _apply(s: GameState) -> None:
        del s
        consume_block_time_combat_grant(context, GRANT_NAME)

    return [
        HookOption(
            choice=Choice("spirits_touch:maneuver", "Spirit's Touch: optional maneuver"),
            apply=_apply,
        )
    ]


hooks.register(INTERCEPT_MODIFIER_HOOK, _provide_spirits_touch_intercept)
hooks.register(MANEUVER_HOOK, _provide_spirits_touch_maneuver)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.INTERCEPT_MODIFIER, Hook.MANEUVER),
        source=__name__,
    )
)
