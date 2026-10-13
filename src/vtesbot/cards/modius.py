"""Modius (crypt vampire ability). krcg id 201703.

Printed text (fetched via krcg's live API, `https://api.krcg.org/card/201703`,
2026-10-11; raw snapshot `data/cards/201703.json`, cross-checked against
`krcg.vtes.VTES[201703].to_json()["card_text"]`, same wording): "Camarilla
Prince of Gary: During the polling step of any referendum, Modius can
discard a master card to get +1 vote."

Rulings (verbatim, via krcg's live API, cross-checked against
`krcg.vtes.VTES[201703].to_json()["rulings"]`, both 2026-10-11):
    - "The ability can be used when in torpor. [LSJ 20011022]"
    - "Cannot be used during a referendum that is automatically passing.
      [PIB 20150105] [LSJ 19980107]"

The second ruling concerns referenda that pass without ever reaching a
normal casting step at all -- per the cited general ruling
(`https://www.vekn.net/forum/rules-questions/68465-voting-is-complicated`,
[LSJ 19980107]): "If a referendum will pass automatically (e.g., Cryptic
Rider, Charming Lobby, Malkavian Rider Clause, Dia de los Muertos), then no
casting votes or ballots occurs during the automatic referendum, and most
'during a political action' and 'during a referendum' effects cannot be
used." None of those auto-passing cards are implemented in this pool, and
`engine/politics.py`'s `resolve_referendum` has no "automatically passing"
code path -- every referendum always goes through a real polling step and
a real `_cast_votes` tally, so this ruling describes a game state this
engine cannot currently produce (not covered by a test; changes no
behaviour here). A future card implementing an auto-passing referendum
must reopen this question for Modius (and any other polling-step ability).

Card type: crypt vampire (`types == ["Vampire"]`). Clan Toreador, title
Prince, group 7, capacity 8, disciplines `["obf", "AUS", "CEL", "PRE"]`.

Timing window: "During the polling step of any referendum" -- the pre-cast
`POLLING_STEP_HOOK` window (`engine/politics.py::_run_pre_cast_hook_window`,
`cards/registry.py::Hook.POLLING_STEP`), offered to both Methuselahs in
alternation for *every* referendum (not only ones Modius's own controller
calls -- "of any referendum", unlike Marcos Belegrad's or Queen Anne's own
"referendum called by <name>" wording). The generic title-vote gate
(`engine/politics.py::_collect_vote_sources`'s `vampire.zone != "ready": continue`)
is the *default* vote-eligibility rule for a titled vampire's own
printed-title vote, but it is not this card's gate: the first ruling above
("can be used when in torpor") overrides it specifically for this printed
ability, so this module checks `vampire.zone in ("ready", "torpor")`
directly (i.e. Modius is in play and controlled, not merely
`"uncontrolled"`/`"burned"`) instead of reusing `_collect_vote_sources`'s
`"ready"`-only gate. `VampireInPlay.locked` is irrelevant either way (same
"whether or not a minion is locked or unlocked does not have any impact on
their ability to vote" rule already generically true of every vote source).

Cost/effect: "can discard a master card" -- optional (not "must"), offered
as a `HookOption` a Methuselah may decline; costs exactly one
`"Master"`-type `LibraryCard` discarded from Modius's controller's hand to
their ash heap -- a plain discard (Rulebook SS8 glossary "Discard: Move a
card in hand to the ash heap"), not a "play": no replacement is drawn from
the library (unlike `engine/phases/discard.py::discard_phase`'s own
"discard phase action", a distinct named rule that does draw one). Which
master card is never a meaningful choice (the text does not single one
out), so no extra `Decision` is raised; mirrors `engine/politics.py::
_burn_one_political_action_card_from_hand`'s "first match in hand order"
convention.

Effect: "+1 vote" -- a new vote source for Modius's controller, added to
`pending["extra_sources"]` (the same `{"source_id", "player", "votes",
"label"}` shape `engine/politics.py`'s own module docstring documents for
exactly this `POLLING_STEP_HOOK` provider shape), then offered and cast like
any other `VoteSource` during `_cast_votes`. Repeatable: the printed text
sets no stated cap ("Modius can discard a master card to get +1 vote", not
"once per referendum" or "(limited)"), so the only real constraint is how
many master cards the controller actually holds -- each use is offered
again (a fresh `HookOption`) for as long as at least one master card
remains in hand, naturally exhausting itself once the hand runs out; no
artificial once-only gate is added here, since the text carries none.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201703
POLLING_STEP_HOOK = "polling_step"
MASTER_CARD_TYPE = "Master"


def _controlled_modius(state: GameState, player: str) -> VampireInPlay | None:
    """Modius, controlled by `player`, in play (ready or torpor -- "can be
    used when in torpor" per the [LSJ 20011022] ruling, module docstring),
    or `None` if `player` does not control a live Modius right now."""
    for vampire in state.players[player].vampires.values():
        if vampire.card.krcg_id == KRCG_ID and vampire.zone in ("ready", "torpor"):
            return vampire
    return None


def _has_master_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.card_type == MASTER_CARD_TYPE for card in state.players[player].hand)


def _discard_one_master_card_from_hand(state: GameState, player: str) -> None:
    """Plain discard (module docstring): move one `"Master"`-type
    `LibraryCard` from `player`'s hand to their ash heap, no replacement
    drawn. Which card, specifically, is never a meaningful choice (same
    reasoning as `engine/politics.py::_burn_one_political_action_card_from_
    hand`), so the first match in hand order is discarded, deterministically.
    `_has_master_card_in_hand` is only ever checked immediately beforehand by
    this module's own provider, so the hand is not expected to have lost its
    only master card between offering and applying -- if it somehow has,
    that is an engine invariant violation, not a legal game state.
    """
    hand = state.players[player].hand
    for index, card in enumerate(hand):
        if card.card_type == MASTER_CARD_TYPE:
            state.players[player].ash_heap.append(hand.pop(index))
            return
    raise AssertionError(
        f"{player} has no master card left in hand to discard for Modius's +1 vote "
        "(engine invariant violation, not a legal game state)"
    )


def _provide_modius(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    modius = _controlled_modius(state, player)
    if modius is None:
        return []
    if not _has_master_card_in_hand(state, player):
        return []

    pending: dict[str, Any] = context["pending"]

    def _apply(s: GameState) -> None:
        _discard_one_master_card_from_hand(s, player)
        suffix = len(pending["extra_sources"])
        pending["extra_sources"].append(
            {
                "source_id": f"modius:{modius.instance_id}:{suffix}",
                "player": player,
                "votes": 1,
                "label": "Modius: discard a master card for +1 vote",
            }
        )

    return [
        HookOption(
            choice=Choice(
                f"modius_discard_master:{modius.instance_id}",
                "Modius [pre]: discard a master card for +1 vote",
            ),
            apply=_apply,
            # `played_card_type` stays at its default `None` (OQ-33, `docs/
            # OPEN_QUESTIONS.md`): this option is Modius's own printed
            # ability being activated, not a card being played -- the
            # discarded master card is this ability's *cost*, never played.
        )
    ]


hooks.register(POLLING_STEP_HOOK, _provide_modius)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Modius",
        status=Status.IMPLEMENTED,
        hooks=(Hook.POLLING_STEP,),
        source=__name__,
    )
)
