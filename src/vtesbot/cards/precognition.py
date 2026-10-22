"""Precognition (Reaction). krcg id 101475.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-17, matching the raw
snapshot saved to `data/cards/101475.json`):
    "[aus] +1 intercept.
    [AUS] As above, and this vampire can prevent 1 damage during the
    first round of the resulting combat if they block."

Rulings (verbatim, via krcg; `cards["Precognition"].rulings`):
    - "[AUS] The damage prevention can only be used if the block is
      successful, and only in the resulting (block-induced) combat."
      [LSJ 20010813]
    - "[AUS] The prevention does not carry over to a follow-up combat
      (eg. Psyche!)." [LSJ 20010819-2]
    - "[AUS] The prevention is provided again if a second block happens
      on the same action (eg. after Form of Mist)." [LSJ 20010814-2]

Card type: Reaction (`types == ["Reaction"]`). `discipline_requirement
== {"type": "Mono", "disciplines": ["aus"]}` -- basic for the `[aus]`
clause, superior for `[AUS]`. `clan_requirement == []`, `cost is None`
(ordinary Reaction, no printed play cost). Legal since 1996-11-27;
confirmed on the active 2P allowed list (`data/formats/2p/
2026-10-03.json`).

Status: implemented. Previously `blocked` (ENG-040,
resolved): the superior clause's damage prevention needed (1) a way for a
reaction played during the block attempt's own stealth/intercept
resolution to hand a grant forward into the specific, later `run_combat`
call for the same vampire, only if it ends up the successful blocker, and
(2) a way for a `DAMAGE_PREVENTION_HOOK` provider to tell "is this round 1
of the current combat." `rules-engineer`'s fix: `engine/action.py::
grant_block_time_combat_effect`/`perform_minion_action`'s own forwarding of
`pending[PENDING_BLOCK_TIME_COMBAT_GRANT_KEY]`, `engine/combat.py::
seed_block_time_combat_grants`/`block_time_combat_grant_available`/
`consume_block_time_combat_grant`, and `engine/damage.py::is_round_one`
(backed by `run_combat`'s own per-round `ROUND_NUMBER_KEY`) -- proven
generically by `tests/rules/test_block_time_combat_grant.py`.

"[aus] +1 intercept.": an unqualified bonus to whichever block attempt is
in progress (`INTERCEPT_MODIFIER_HOOK`), same reading as `cards/
second_tradition_domain.py`'s own clause-1 docstring (intercept is a
property of the attempt, not tied to the playing vampire's identity beyond
eligibility to play the card) -- offered to any of the defender's own
ready, unlocked Auspex vampires, mirroring that module's `_eligible_
unlocked` shape with an "aus"/"AUS" discipline gate instead of a title
gate.

"[AUS] As above, and this vampire can prevent 1 damage during the first
round of the resulting combat if they block.": superior Auspex vampires
are additionally offered a second option for the *same* physical card,
Rulebook §3 "may opt to use either the basic ... or the superior ...
effect" (`cards/soak.py`'s own precedent for offering both levels
separately rather than only the higher one). Its own `apply` plays the
card and records a `GRANT_NAME` block-time combat grant for *this specific
vampire* via `grant_block_time_combat_effect`, read back by `perform_
minion_action` only if this exact vampire ends up the successful blocker
[LSJ 20010813] -- "this vampire ... if they block" needs no extra
engine-side identity check beyond that, since the grant is already keyed
by instance id. The `DAMAGE_PREVENTION_HOOK` provider below then gates on
*both* `is_round_one(round_state)` and `block_time_combat_grant_available`
-- an unconsumed grant (no damage in round 1) must not still apply in
round 2 [LSJ 20010819-2]; it is never forwarded into a second, later
`run_combat` call either, satisfying the same ruling for any hypothetical
follow-up combat. [LSJ 20010814-2]'s "provided again if a second block
happens on the same action" needs no special-case code: nothing here ever
marks the card as permanently spent beyond the standard "no card is played
twice per action by the same vampire" cap (`USED_BY_KEY`, mirrors `cards/
second_tradition_domain.py`'s own `USED_BY_KEY`) -- a *second*, separate
block attempt within the same action that re-reaches the stealth/intercept
ping-pong (not reachable by any mechanism implemented in this project
today, e.g. a dissolved-blocker-triggers-a-new-attempt effect like Form of
Mist) would simply let this same provider offer and record a fresh grant
again, since `USED_BY_KEY` only blocks a second use *within the same
attempt's own `pending` dict scope established by the project's own
engine, not across attempts of a kind this project has no engine support
for yet.

"Prevent 1 damage" (unqualified, no "non-aggravated" qualifier unlike
Soak): mirrors `cards/rolling_with_the_punches.py`'s own `[for]` clause --
reduces whichever damage type (normal or aggravated) is actually present
by 1 point; both being simultaneously positive is an engine invariant
violation (`apply_damage`'s only production call site, `engine/combat.py::
_resolve_strike_pair`, always passes a single type per call), surfaced
loudly rather than silently resolved.

Eligibility mirrors `second_tradition_domain.py`'s own `_eligible_unlocked`
shape: `player`'s own ready, unlocked vampires with `"aus"` or `"AUS"` in
`card.disciplines` (plain printed stat, not attachment-aware `effective_
disciplines` -- ENG-002 noted, not acted on here, matching every other
discipline-gated card in this project) that have not already played this
exact card this action.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import INTERCEPT_MODIFIER_HOOK, grant_block_time_combat_effect
from vtesbot.engine.combat import block_time_combat_grant_available, consume_block_time_combat_grant
from vtesbot.engine.damage import (
    DAMAGE_PREVENTION_HOOK,
    ROUND_STATE_CONTEXT_KEY,
    is_round_one,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101475
NAME = "Precognition"
BASIC = "aus"
SUPERIOR = "AUS"
INTERCEPT_BONUS = 1
"""Verbatim "+1 intercept."."""
GRANT_NAME = "precognition_round_one_prevention"
"""`engine/combat.py::BLOCK_TIME_COMBAT_GRANT_KEY`'s own per-grant name for
this card's superior clause -- never read by any other card."""
USED_BY_KEY = "precognition_used_by"
"""§8 glossary "A minion cannot play the same reaction card more than once
during a single action" -- shared between both clauses (same physical
card), mirrors `cards/second_tradition_domain.py`'s own `USED_BY_KEY`."""
CARD_TYPE = "Reaction"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Reaction" docstring fact above. The later
`DAMAGE_PREVENTION_HOOK` option (claiming an already-earned grant, not
playing a card) leaves this at its default `None`, mirroring `cards/
saku_pihlajamaki.py`'s own precedent for a claimed-not-played grant."""


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


def _provide_precognition_intercept(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[aus] +1 intercept." and "[AUS] As above, and this vampire can
    prevent 1 damage during the first round of the resulting combat if
    they block." -- see module docstring for each clause's own gates."""
    player = context["player"]  # INTERCEPT_MODIFIER_HOOK is only ever offered to the defender.
    if not _has_card_in_hand(state, player):
        return []

    used_by = _used_by(context.get("pending"))
    eligible = _eligible(state, player, used_by)
    if not eligible:
        return []
    pending = context.get("pending")

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
                    f"precognition:basic:{vampire.instance_id}",
                    f"Precognition [aus]: +{INTERCEPT_BONUS} intercept ({vampire.card.name})",
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
                        f"precognition:superior:{vampire.instance_id}",
                        f"Precognition [AUS]: +{INTERCEPT_BONUS} intercept, prevent 1 damage in "
                        f"round 1 if they block ({vampire.card.name})",
                    ),
                    apply=_make_superior(vampire),
                    played_card_type=CARD_TYPE,
                )
            )
    return options


def _provide_precognition_prevention(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """The superior clause's own damage-prevention half, claimed (not
    played) once the grant it recorded has survived into round 1 of the
    resulting combat -- see module docstring."""
    del state
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if not is_round_one(round_state):
        return []
    if not block_time_combat_grant_available(context, GRANT_NAME):
        return []
    damage_box = context["damage"]
    normal = damage_box.get("normal", 0)
    aggravated = damage_box.get("aggravated", 0)
    if normal <= 0 and aggravated <= 0:
        return []
    if normal > 0 and aggravated > 0:
        raise AssertionError(
            "precognition: damage_box has both normal and aggravated damage at once, "
            "which no production call site produces today (engine invariant violation, "
            "not a legal game state)"
        )

    def _apply(s: GameState) -> None:
        del s
        consume_block_time_combat_grant(context, GRANT_NAME)
        if aggravated > 0:
            damage_box["aggravated"] = aggravated - 1
        else:
            damage_box["normal"] = normal - 1

    return [
        HookOption(
            choice=Choice("precognition:prevent", "Precognition: prevent 1 damage"), apply=_apply
        )
    ]


hooks.register(INTERCEPT_MODIFIER_HOOK, _provide_precognition_intercept)
hooks.register(DAMAGE_PREVENTION_HOOK, _provide_precognition_prevention)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.INTERCEPT_MODIFIER, Hook.DAMAGE_PREVENTION),
        source=__name__,
    )
)
