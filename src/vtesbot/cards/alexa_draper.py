"""Alexa Draper (crypt vampire ability). krcg id 201529.

Printed text (verbatim, via the installed `krcg` package, `from krcg import
vtes; vtes.VTES.load(); vtes.VTES[201529].card_text`, re-verified live
2026-10-15, matching `data/cards/201529.json`): "Camarilla Prince of
Melbourne: During the polling step of any referendum, Alexa can discard a
card requiring Dominate [dom] to get +1 vote." Clan Ventrue, title Prince,
group 6, capacity 8, disciplines `["for", "pot", "DOM", "PRE"]`.

Ruling (verbatim, via krcg, re-verified live 2026-10-15 -- this is the
*only* ruling on file for this card; an earlier draft of this module's
docstring also cited the "automatically passing referendum" ruling, but
that ruling is not actually attached to 201529 live, only to Modius/
Scalpel Tongue/Perfect Paragon -- dropped here, not guessed back in):
    - "The ability can be used while locked, only once per referendum."
      [ANK 20220705]

Timing window: "During the polling step of any referendum" -- the generic
`engine/politics.py::POLLING_STEP_HOOK`, offered at both the pre-cast
window and every mid-cast turn of *every* referendum (not only ones
Alexa's own controller calls -- "of any referendum", same reading as
Modius's identical construction, `cards/modius.py`). That dispatch never
gates an offer on any vampire's `locked` state
(`_run_pre_cast_hook_window`/`_cast_votes`), so "usable while locked"
needs no extra code -- just no `is_ready_unlocked` gate, which would
wrongly exclude a locked-but-ready Alexa. Gated instead on
`vampire.zone == "ready"` (she must be in play and not in torpor): unlike
Modius, no ruling here licenses use from torpor, so the ordinary default
(an untorpid vampire) applies.

"Discard a card requiring Dominate [dom]": identifying which of the
arbitrary cards in Alexa's controller's hand print a Dominate requirement
uses `engine/cards.py::LibraryCard.discipline_requirement` /
`requires_discipline` (added by `rules-engineer` for exactly this clause).
`requires_discipline` is deliberately level-agnostic (lowercase trigrams
only): which level a play would use is a property of how a card is
*played*, not of what it requires while sitting in hand -- settled by
"When played, a multi-Disciplines card counts as requiring the
Discipline(s) being used. In the hand, library, or ash heap, the card is
considered to require any and/or all Disciplines listed on it."
[LSJ 20011204-3] [PIB 20130704] (the same ruling `line_brawl.py` cites for
its own in-hand collapsing). A discarded-from-hand card is exactly this
situation, so no basic/superior distinction is needed and no Open
Question is raised. One `HookOption` is offered per qualifying hand card
(mirrors `scalpel_tongue.py`'s one-option-per-target shape), each
discarding that specific card (plain discard, Rulebook §8 glossary: no
replacement drawn) for a `pending["extra_sources"]` +1 vote (the generic
`POLLING_STEP_HOOK` vote-source shape, `modius.py`/`perfect_paragon.py`).

"Only once per referendum" [ANK 20220705]: tracked via a
`context["pending"]` flag (`PENDING_USED_KEY`), the same mechanism
`diana_iadanza.py`'s own once-per-referendum cap uses -- naturally scoped
to one `resolve_referendum` call, since `pending` is a fresh dict per call
(`engine/politics.py`). Once set, no further option is offered for the
rest of that referendum, even for a different qualifying hand card.

Status: implemented.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.cards import requires_discipline
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.politics import POLLING_STEP_HOOK
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201529
DOMINATE = "dom"
PENDING_USED_KEY = "alexa_draper_used"


def _controlled_ready_alexa(state: GameState, player: str) -> VampireInPlay | None:
    """Alexa, controlled by `player`, `zone == "ready"` (module docstring:
    no ruling licenses use from torpor, unlike Modius)."""
    for vampire in state.players[player].vampires.values():
        if vampire.card.krcg_id == KRCG_ID and vampire.zone == "ready":
            return vampire
    return None


def _dominate_requiring_hand_cards(state: GameState, player: str) -> list[Any]:
    """Hand cards whose printed discipline requirement includes Dominate
    (module docstring's `requires_discipline` citation)."""
    return [
        card
        for card in state.players[player].hand
        if requires_discipline(card.discipline_requirement, DOMINATE)
    ]


def _discard_one_card_from_hand_by_krcg_id(state: GameState, player: str, krcg_id: int) -> None:
    """Plain discard (module docstring): first matching `krcg_id` in hand
    order, moved to ash heap, no replacement drawn. Duplicate copies of the
    same card are interchangeable, so "first match" is correct regardless
    of which offered option (per-card, not per-index) was chosen -- same
    reasoning as `modius.py`'s own helper."""
    hand = state.players[player].hand
    for index, card in enumerate(hand):
        if card.krcg_id == krcg_id:
            state.players[player].ash_heap.append(hand.pop(index))
            return
    raise AssertionError(
        f"{player} has no krcg_id={krcg_id} Dominate-requiring card left in hand to discard "
        "for Alexa Draper's +1 vote (engine invariant violation, not a legal game state)"
    )


def _provide_alexa_draper(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    alexa = _controlled_ready_alexa(state, player)
    if alexa is None:
        return []
    pending = context.get("pending")
    if pending is None or pending.get(PENDING_USED_KEY, False):
        return []

    options: list[HookOption] = []
    for index, card in enumerate(_dominate_requiring_hand_cards(state, player)):
        krcg_id = card.krcg_id

        def _apply(s: GameState, krcg_id: int = krcg_id) -> None:
            _discard_one_card_from_hand_by_krcg_id(s, player, krcg_id)
            pending[PENDING_USED_KEY] = True
            pending["extra_sources"].append(
                {
                    "source_id": f"alexa_draper:{alexa.instance_id}",
                    "player": player,
                    "votes": 1,
                    "label": "Alexa Draper: discard a card requiring Dominate for +1 vote",
                }
            )

        options.append(
            HookOption(
                choice=Choice(
                    f"alexa_draper:{index}:{krcg_id}",
                    f"Alexa Draper [dom]: discard {card.name} (requires Dominate) for +1 vote",
                ),
                apply=_apply,
                # `played_card_type` stays at its default `None`: this option
                # is Alexa's own printed ability being activated, not a card
                # being played -- the discarded card is the ability's cost,
                # never played (same reasoning as `modius.py`).
            )
        )
    return options


hooks.register(POLLING_STEP_HOOK, _provide_alexa_draper)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Alexa Draper",
        status=Status.IMPLEMENTED,
        hooks=(Hook.POLLING_STEP,),
        source=__name__,
    )
)
