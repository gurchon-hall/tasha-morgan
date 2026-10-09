"""Threats (Action Modifier). krcg id 101978.

Card text (fetched via krcg 5.14+, `krcg.load()["Threats"].text`,
2026-10-09; raw snapshot `data/cards/101978.json`):
    "Only usable during a bleed action.
    [dom] +1 bleed (limited).
    [DOM] +2 bleed (limited)."

Rulings: none on file -- `krcg.load()["Threats"].rulings == []`,
cross-checked against `https://api.krcg.org/card/101978` (2026-10-09, same
empty list).

Card type: Action Modifier. `discipline_requirement.disciplines == ["dom"]`
(basic Dominate required; superior Dominate, printed uppercase `"DOM"` on a
`CryptCard`, additionally unlocks the bold-text effect -- Rulebook SS3
"Discipline symbol within a diamond ... may opt to use either the basic
(plain text) or the superior (bold) effect ... but not both"). `cost is
None` (free).

"Only usable during a bleed action": trivially satisfied by which hook this
card registers against -- `"bleed_amount_modifier"` is only ever offered
from `engine/phases/minion.py::_perform_bleed`'s `resolve()`, never from
`_perform_hunt`, so this restriction needs no extra check here.

"Action modifier card": per Rulebook SS2 Cards in general, "The acting
minion can play these cards to modify their action at any time before
action resolution." -- played only by the *acting* (bleeding) minion, never
by the defender. Within the two-sided `"bleed_amount_modifier"` impulse
window the hook shares with reducing reaction cards (e.g. Telepathic
Counter), this provider only offers anything when the window's current
`context["player"]` is in fact that acting minion's own controller (checked
by looking the acting vampire up in `context["player"]`'s own `vampires`
dict).

"(limited)" (SS8 glossary): "an action modifier card cannot be played to
increase the bleed if the bleed amount is already being increased by
another action modifier card" -- and SS2 "A minion cannot play the same
action modifier card more than once during a single action (even if using a
different Discipline level)". Since there is only one acting minion per
bleed action, both rules collapse to the same enforcement here: once
Threats (at either level) has been played once in this action, it (and any
future "(limited)" bleed-increase action modifier) is not offered again,
tracked via the per-action `bleed_bookkeeping` scratch space shared with
`telepathic_counter.py` (see `vtesbot.cards._shared`).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import bleed_bookkeeping, play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101978
BLEED_AMOUNT_MODIFIER_HOOK = "bleed_amount_modifier"
LIMITED_USED_KEY = "bleed_increase_limited_used"


def _provide_threats(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    acting_vampire_id = context["vampire"]
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None:
        return []  # `player` is the defender this turn of the impulse window, not the bleeder.

    disciplines = acting_vampire.card.disciplines
    if "dom" not in disciplines and "DOM" not in disciplines:
        return []
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    amount_box = context["amount"]
    book = bleed_bookkeeping(amount_box)
    if book.get(LIMITED_USED_KEY):
        return []

    def _make_apply(delta: int) -> Any:
        def _apply(s: GameState) -> None:
            play_from_hand(s, player, KRCG_ID)
            amount_box[0] += delta
            book[LIMITED_USED_KEY] = True

        return _apply

    options = [
        HookOption(
            choice=Choice("threats:basic", "Threats [dom]: +1 bleed (limited)"),
            apply=_make_apply(1),
        )
    ]
    if "DOM" in disciplines:
        options.append(
            HookOption(
                choice=Choice("threats:superior", "Threats [DOM]: +2 bleed (limited)"),
                apply=_make_apply(2),
            )
        )
    return options


hooks.register(BLEED_AMOUNT_MODIFIER_HOOK, _provide_threats)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Threats",
        status=Status.IMPLEMENTED,
        hooks=(Hook.BLEED_AMOUNT_MODIFIER,),
        source=__name__,
    )
)
