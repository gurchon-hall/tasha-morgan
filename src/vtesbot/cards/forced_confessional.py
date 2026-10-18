"""Forced Confessional (Action Modifier). krcg id 102250.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-18, matching the raw
snapshot saved to `data/cards/102250.json`):
    "Only usable if a minion attempts to block.
    [dom] The blocking minion gets -1 intercept.
    [DOM] That attempt fails and the blocking minion cannot attempt to
    block this action again."

Rulings: none on file -- `krcg.load()[102250].rulings == []`.

Card type: Action Modifier. `clan_requirement == ["Salubri"]` (only a
Salubri vampire may play this card at all -- Rulebook §2 "Requirements for
Playing Cards"); `discipline_requirement == {"type": "Mono", "disciplines":
["dom"]}`, basic Dominate for the `[dom]` clause, superior for `[DOM]`.
`cost is None` (free). Legal since 2024-01-31; confirmed on the active 2P
allowed list (`data/formats/2p/2026-10-03.json`) and in the suggested 2P
decklist `data/decks/vekn-2p/salubri.json` (2 copies).

Status: implemented (OQ-65, `docs/OPEN_QUESTIONS.md`, resolved -- the
engine gap this card's superior clause was blocked on,
`engine/action.py::FORCE_BLOCK_ATTEMPT_FAILURE_HOOK`, was built this pass).
Both clauses are played by the *acting* minion, against the *defender's*
current blocker -- the opposite shape from `cards/eyes_of_argus.py`/`cards/
spirits_touch.py`'s own defender-played Reactions, despite being one more
Salubri/Dominate "basic vs superior" card like `cards/bonding.py`.

"Only usable if a minion attempts to block.": both clauses register against
hooks only ever offered once `engine/action.py::_duel_stealth_intercept` has
a specific blocker fixed (`context["blocking_vampire"]` always set there,
never at `attempt_block`'s own earlier proactive offer point, which carries
no such key at all) -- gated by `context.get("blocking_vampire") is not
None`, degrading to "not usable" when that context is missing, never a
guess (same convention `cards/organized_resistance.py`'s own docstring
documents for an identical "blocking_vampire" read).

"[dom] The blocking minion gets -1 intercept.": wired against the
pre-existing `INTERCEPT_DECREASE_HOOK` (OQ-30/31), only ever offered in
`_duel_stealth_intercept`'s own "block currently succeeds" branch (the only
moment a numeric intercept penalty has any observable effect -- "only when
needed", same scoping as `bonding.py`'s own superior clause), merged into
one `Decision` alongside the engine's existing `STEALTH_MODIFIER_HOOK`/
`STEALTH_INCREASE_HOOK`/`FORCE_BLOCK_ATTEMPT_FAILURE_HOOK` choices there.
Unlike Perfect Paragon's own "younger vampires" qualifier (a property class,
re-checked against *whichever* candidate is later fixed), "the blocking
minion" is one specific, already-identified vampire -- the
`ActiveInterceptDecrease.qualifies` predicate captures
`context["blocking_vampire"]` by `instance_id` at play time, so the penalty
never leaks onto a different vampire's later, separate block attempt within
the same action.

"[DOM] That attempt fails and the blocking minion cannot attempt to block
this action again.": wired against the new `FORCE_BLOCK_ATTEMPT_FAILURE_
HOOK` (OQ-65). `apply()` adds the fixed blocking vampire's own `instance_id`
to `pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY]` directly (same
convention `cards/seduction.py`/`cards/sleeping_mind.py` use from
`BLOCK_CANDIDATE_EXCLUSION_HOOK`'s own proactive offer point) for the
"cannot attempt ... again" half, and lets the hook's own `forced_failure`
return value handle "that attempt fails" outright -- `attempt_block`'s
retry loop re-reads the exclusion set fresh on every pass, so the named
vampire is never offered as a candidate again (hardcoded or injected) for
the rest of this one action, while any other vampire remains unaffected.
Unlike the basic clause, this hook is offered to the actor in *both*
branches of `_duel_stealth_intercept` (rules-auditor finding, `FORCE_BLOCK_
ATTEMPT_FAILURE_HOOK`'s own docstring): "cannot attempt to block this action
again" has nothing to do with whether the attempt is currently succeeding
or already failing on the raw numbers (Rulebook §4 "Resolve Any Block
Attempts": a failed attempt may be retried "as often as the blocking
Methuselah wishes"), so the exclusion option is offered to the actor even
while the current blocker is already failing on the numbers alone, not
merged with any numeric modifier there since none of those are "needed".

Discipline/clan gates: both providers check the acting vampire
(`context["acting_vampire"]`, the only vampire `INTERCEPT_DECREASE_HOOK`/
`FORCE_BLOCK_ATTEMPT_FAILURE_HOOK` are ever offered on behalf of) for both
`card.clan == "Salubri"` and the appropriate Dominate level, plus the
physical card in `player`'s own hand -- mirrors `cards/forty_seventh_
street_royals.py`'s own `acting_vampire.card.clan` read and `cards/bonding.
py`'s own basic/superior discipline split.

"(Action modifier card)" per-action cap (§2 "A minion cannot play the same
action modifier card more than once during a single action"): needs no
extra bookkeeping -- both clauses consume the one physical card via
`play_from_hand` the instant either is chosen, and both providers re-check
hand membership fresh on every offer, so a second attempt within the same
action only ever sees this card if a second physical copy remains in hand
(same reasoning `perfect_paragon.py`'s own docstring documents for its own
two-clauses-one-card shape).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    FORCE_BLOCK_ATTEMPT_FAILURE_HOOK,
    INTERCEPT_DECREASE_HOOK,
    PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY,
    PENDING_INTERCEPT_DECREASE_KEY,
    ActiveInterceptDecrease,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 102250
NAME = "Forced Confessional"
CLAN = "Salubri"
BASIC = "dom"
SUPERIOR = "DOM"
INTERCEPT_DELTA = -1
"""Verbatim "The blocking minion gets -1 intercept."."""
CARD_TYPE = "Action Modifier"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Action Modifier" docstring fact above."""


def _acting_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    """The vampire performing the modified action -- both hooks this module
    registers against are only ever offered to its own controller."""
    acting_vampire_id = context.get("acting_vampire")
    if acting_vampire_id is None:
        return None
    return state.players[context["player"]].vampires.get(acting_vampire_id)


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _blocking_vampire_id(context: Mapping[str, Any]) -> str | None:
    """ "Only usable if a minion attempts to block." -- see module
    docstring for why `context.get("blocking_vampire")` is the gate."""
    return context.get("blocking_vampire")


def _provide_forced_confessional_basic(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[dom] The blocking minion gets -1 intercept." -- see module
    docstring for the `qualifies` predicate's "this one blocker only"
    scope."""
    acting_vampire = _acting_vampire(state, context)
    if acting_vampire is None:
        return []
    if acting_vampire.card.clan != CLAN:
        return []
    disciplines = acting_vampire.card.disciplines
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    blocking_vampire_id = _blocking_vampire_id(context)
    if blocking_vampire_id is None:
        return []
    pending = context.get("pending")
    if pending is None:
        return []  # no scratch container to record the persistent modifier into.

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        modifiers = pending.setdefault(PENDING_INTERCEPT_DECREASE_KEY, [])
        modifiers.append(
            ActiveInterceptDecrease(
                delta=INTERCEPT_DELTA,
                qualifies=lambda v: v.instance_id == blocking_vampire_id,
            )
        )

    return [
        HookOption(
            choice=Choice(
                "forced_confessional:basic",
                "Forced Confessional [dom]: the blocking minion gets -1 intercept",
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_forced_confessional_superior(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[DOM] That attempt fails and the blocking minion cannot attempt to
    block this action again." -- see module docstring for the two-part
    `apply`."""
    acting_vampire = _acting_vampire(state, context)
    if acting_vampire is None:
        return []
    if acting_vampire.card.clan != CLAN:
        return []
    if SUPERIOR not in acting_vampire.card.disciplines:
        return []
    player = context["player"]
    if not _has_card_in_hand(state, player):
        return []
    blocking_vampire_id = _blocking_vampire_id(context)
    if blocking_vampire_id is None:
        return []
    pending = context.get("pending")
    if pending is None:
        return []  # no scratch container to record the exclusion into.

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        pending.setdefault(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()).add(blocking_vampire_id)

    return [
        HookOption(
            choice=Choice(
                "forced_confessional:superior",
                "Forced Confessional [DOM]: that attempt fails; the blocking minion "
                "cannot attempt to block this action again",
            ),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(INTERCEPT_DECREASE_HOOK, _provide_forced_confessional_basic)
hooks.register(FORCE_BLOCK_ATTEMPT_FAILURE_HOOK, _provide_forced_confessional_superior)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.INTERCEPT_DECREASE, Hook.FORCE_BLOCK_ATTEMPT_FAILURE),
        source=__name__,
    )
)
