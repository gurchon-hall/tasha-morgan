"""Eyes of Argus (Reaction). krcg id 100680.

Card text (verbatim, via `krcg.load()` + `msgspec.json.encode()` in the
project's `uv run` virtualenv (krcg 5.14), 2026-10-18, matching the raw
snapshot saved to `data/cards/100680.json`):
    "[aus] Only usable during an action directed at you (or a card you
    control). +2 intercept.
    [AUS] Only usable by a locked vampire. This vampire wakes (they ignore
    the requirement to be unlocked for playing reaction cards and
    attempting to block until the end of the action)."

Rulings (verbatim, via krcg; `cards["Eyes of Argus"].rulings`):
    - "[AUS] The minion need not attempt to block nor play further reaction
      cards: that is merely an option." [TOM 19951129]
    - "[AUS] Can be played or used after action resolution (e.g. to use a
      reaction card like {Fast Reaction} after combat)." [LSJ 20091123]
    - "[AUS] Can be played or used during the 'as a card is played' window,
      except in combat, or when there is no action." [ANK 20210817]

Card type: Reaction (`types == ["Reaction"]`). `discipline_requirement ==
{"type": "Mono", "disciplines": ["aus"]}` -- basic Auspex for the `[aus]`
clause, superior for `[AUS]`. `clan_requirement == []`, `cost is None`
(ordinary Reaction, no printed play cost). Legal since 2008-12-19;
confirmed on the active 2P allowed list (`data/formats/2p/2026-10-03.json`)
and in the suggested 2P decklist `data/decks/vekn-2p/salubri.json`
(2 copies).

Status: implemented. Two clauses, two different hooks, same physical card
-- the exact shape already used by `cards/bonding.py` (different basic vs
superior restrictions) and `cards/on_the_qui_vive.py` (the wake mechanic
itself):

"[aus] Only usable during an action directed at you (or a card you
control). +2 intercept." (the basic clause): a `INTERCEPT_MODIFIER_HOOK`
provider, offered only to the defender, same shape as `cards/
precognition.py`'s own `[aus] +1 intercept.` clause but gated by one extra
restriction. `INTERCEPT_MODIFIER_HOOK`'s own context always carries
`"directed"` (`engine/action.py::_duel_stealth_intercept`'s context dict),
the same `bool` `engine/phases/minion.py` sets per action type: `True` for
bleed (targets the bled Methuselah) and for diablerie against the other
controller's torpid vampire (targets that controller's own card), `False`
for hunt (targets the Edge, no Methuselah or card) and for diablerie
against the acting player's own torpid vampire. In every `directed=True`
case in this codebase the action's own target is exactly the defender
Methuselah or a card the defender controls -- CLAUDE.md §3's 2P structural
fact (there is only ever one other Methuselah to be `defender` at all)
rules out a third party the restriction could otherwise mean. So
`context["directed"] is True` is read directly as "directed at you (or a
card you control)", no RUL entry needed. Eligibility otherwise mirrors
`precognition.py`'s own `_eligible` shape: `player`'s own ready, unlocked
vampires with `"aus"` or `"AUS"` in `card.disciplines`.

"[AUS] Only usable by a locked vampire. This vampire wakes (...)." (the
superior clause): registered against `WAKE_LOCKED_MINION_HOOK`, an exact
copy of `on_the_qui_vive.py`'s own wake mechanism (eligibility: `player`'s
own locked, not-yet-`woken` vampires; `apply` plays the card and sets
`woken = True`) with one addition -- gated on `"AUS"` in `card.
disciplines` (superior Auspex only; unlike On the Qui Vive, which has no
discipline requirement at all). [TOM 19951129] ("need not attempt to block
nor play further reaction cards") needs no extra code, same reasoning as
On the Qui Vive's own docstring: the woken state's only value is the
optional eligibility it grants.

[LSJ 20091123]/[ANK 20210817] (additional play windows: after action
resolution; during the "as a card is played" window; or with no action at
all): the identical scope decision already made and explained in `cards/
on_the_qui_vive.py`'s own docstring applies verbatim here -- neither
describes a further mandatory effect, and this engine has no dispatch
point modeling "no action in progress at all" or a generic "as any card is
played" moment yet. Not acted on; noted, not silently dropped.

"A minion cannot play the same reaction card more than once during a
single action" (§8 glossary, generic rule, not printed on this card):
tracked via a `USED_BY_KEY` set in `pending`, shared by both clauses
(mirrors `precognition.py`'s own identically-shaped cap across its own two
clauses of one physical card) -- a vampire that has used either clause of
Eyes of Argus this action cannot use the other, or the same clause again
with a second physical copy.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import INTERCEPT_MODIFIER_HOOK, WAKE_LOCKED_MINION_HOOK
from vtesbot.engine.attachments import effective_disciplines
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100680
NAME = "Eyes of Argus"
BASIC = "aus"
SUPERIOR = "AUS"
INTERCEPT_BONUS = 2
"""Verbatim "+2 intercept."."""
USED_BY_KEY = "eyes_of_argus_used_by"
"""`pending[...]` key: a `set[str]` of vampire instance ids that have
already played either clause of this card this action (module docstring,
mirrors `cards/precognition.py`'s own `USED_BY_KEY`)."""
CARD_TYPE = "Reaction"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Reaction" docstring fact above."""


def _used_by(pending: dict[str, Any] | None) -> set[str]:
    if pending is None:
        return set()
    return pending.setdefault(USED_BY_KEY, set())


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _eligible_basic(state: GameState, player: str, used_by: set[str]) -> list[VampireInPlay]:
    """ "[aus] ... +2 intercept.": `player`'s own ready, unlocked vampires
    with basic or superior Auspex, not already used this action."""
    return [
        v
        for v in state.players[player].vampires.values()
        if v.is_ready_unlocked
        and v.instance_id not in used_by
        and (
            BASIC in effective_disciplines(state, v) or SUPERIOR in effective_disciplines(state, v)
        )
    ]


def _eligible_superior(state: GameState, player: str, used_by: set[str]) -> list[VampireInPlay]:
    """ "[AUS] Only usable by a locked vampire. This vampire wakes ...":
    `player`'s own locked, not-yet-`woken` vampires with superior Auspex,
    not already used this action."""
    return [
        v
        for v in state.players[player].vampires.values()
        if v.zone == "ready"
        and v.locked
        and not v.woken
        and v.instance_id not in used_by
        and SUPERIOR in effective_disciplines(state, v)
    ]


def _provide_eyes_of_argus_intercept(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[aus] Only usable during an action directed at you (or a card you
    control). +2 intercept." -- see module docstring for the
    `context["directed"]` reading."""
    if context.get("directed") is not True:
        return []
    player = context["player"]  # INTERCEPT_MODIFIER_HOOK is only ever offered to the defender.
    if not _has_card_in_hand(state, player):
        return []

    pending = context.get("pending")
    used_by = _used_by(pending)
    eligible = _eligible_basic(state, player, used_by)

    options: list[HookOption] = []
    for vampire in eligible:

        def _make_apply(v: VampireInPlay) -> Any:
            def _apply(s: GameState) -> int:
                play_from_hand(s, player, KRCG_ID)
                used_by.add(v.instance_id)
                return INTERCEPT_BONUS

            return _apply

        options.append(
            HookOption(
                choice=Choice(
                    f"eyes_of_argus:basic:{vampire.instance_id}",
                    f"Eyes of Argus [aus]: +{INTERCEPT_BONUS} intercept ({vampire.card.name})",
                ),
                apply=_make_apply(vampire),
                played_card_type=CARD_TYPE,
            )
        )
    return options


def _provide_eyes_of_argus_wake(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[AUS] Only usable by a locked vampire. This vampire wakes
    (...)." -- an exact copy of `on_the_qui_vive.py`'s own wake mechanism,
    gated additionally on superior Auspex (see module docstring)."""
    player = context["player"]  # WAKE_LOCKED_MINION_HOOK is only ever offered to the defender.
    if not _has_card_in_hand(state, player):
        return []

    pending = context.get("pending")
    used_by = _used_by(pending)
    eligible = _eligible_superior(state, player, used_by)

    def _make_apply(vampire: VampireInPlay) -> Any:
        def _apply(s: GameState) -> None:
            play_from_hand(s, player, KRCG_ID)
            used_by.add(vampire.instance_id)
            vampire.woken = True

        return _apply

    return [
        HookOption(
            choice=Choice(
                f"eyes_of_argus:superior:{vampire.instance_id}",
                f"Eyes of Argus [AUS]: wake {vampire.card.name}",
            ),
            apply=_make_apply(vampire),
            played_card_type=CARD_TYPE,
        )
        for vampire in eligible
    ]


hooks.register(INTERCEPT_MODIFIER_HOOK, _provide_eyes_of_argus_intercept)
hooks.register(WAKE_LOCKED_MINION_HOOK, _provide_eyes_of_argus_wake)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name=NAME,
        status=Status.IMPLEMENTED,
        hooks=(Hook.INTERCEPT_MODIFIER, Hook.WAKE_LOCKED_MINION),
        source=__name__,
    )
)
