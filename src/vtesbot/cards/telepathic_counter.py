"""Telepathic Counter (Reaction). krcg id 101948.

Card text (fetched via krcg 5.14+, `krcg.load()["Telepathic Counter"].text`,
2026-10-09; raw snapshot `data/cards/101948.json`):
    "[aus] Reduce a bleed against you by 1.
    [AUS] Reduce a bleed against you by 2."

Rulings (verbatim, via krcg, cross-checked against
`https://api.krcg.org/card/101948`, 2026-10-09):
    - "Must be played before the bleed can be considered successful (eg.
      before [OBF] {101857|Spying Mission}), but can be played before or
      after block attempts." [TOM 19960303] [LSJ 20061212]

Card type: Reaction. `discipline_requirement.disciplines == ["aus"]`
(basic Auspex required to play at all; superior Auspex, printed uppercase
`"AUS"` on a `CryptCard`, additionally unlocks the bold-text effect --
Rulebook SS3 "Discipline symbol within a diamond ... may opt to use either
the basic (plain text) or the superior (bold) effect ... but not both").
`cost is None` (free).

Timing window: "a bleed against you" -- the defending Methuselah's reaction,
played by one of *their* ready, unlocked minions (SS8 glossary "Reaction
Card: A card played by a Methuselah's ready, unlocked minion in response to
an action taken by a minion controlled by another Methuselah"; SS2 "A
minion cannot play the same reaction card more than once during a single
action (even if using a different Discipline level)" -- restricts the same
*minion*, not the whole Methuselah: two different eligible minions may each
play their own copy in the same bleed). Implemented against the already
wired, two-sided `"bleed_amount_modifier"` impulse window
(`engine/hooks.py`, `engine/phases/minion.py::_perform_bleed`): the window
alternates between the acting (bleeding) player and the defending player,
so this card's provider only offers anything on the defending player's own
turn in that alternation -- determined by checking whether the acting
vampire (`context["vampire"]`) belongs to `context["player"]`'s own
`vampires` dict (if it does, `context["player"]` is the bleeder, not the
defender, and nothing is offered).

Ruling timing note: the engine only opens the `"bleed_amount_modifier"`
window once the bleed action is already unblocked (`_perform_bleed`'s
`resolve()`, called after the block-attempt phase concludes), i.e. strictly
"after block attempts". The ruling also allows playing it *before* block
attempts; but the bleed amount has no bearing on stealth/intercept or on
whether a block attempt itself succeeds, so resolving the reduction only
at `resolve()` time produces byte-for-byte the same final pool loss and Edge
result as playing it earlier would -- not a missing hook, just a timing
window with no observable difference for this specific card.

"Reduce a bleed against you by N": clamped at 0 by `_perform_bleed`'s own
`amount = max(0, amount_box[0])`, already covering the case where the total
reduction exceeds the (possibly further-increased) bleed amount.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import bleed_bookkeeping, play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101948
BLEED_AMOUNT_MODIFIER_HOOK = "bleed_amount_modifier"
USED_BY_KEY = "telepathic_counter_used_by"


def _is_defender(state: GameState, player: str, acting_vampire_id: str) -> bool:
    """`player` is the Methuselah being bled against iff the acting (bleeding)
    vampire is not one of their own."""
    return acting_vampire_id not in state.players[player].vampires


def _eligible_vampires(state: GameState, player: str, used_by: set[str]) -> list[VampireInPlay]:
    return [
        v
        for v in state.players[player].vampires.values()
        if v.is_ready_unlocked
        and v.instance_id not in used_by
        and ("aus" in v.card.disciplines or "AUS" in v.card.disciplines)
    ]


def _provide_telepathic_counter(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    acting_vampire_id = context["vampire"]
    if not _is_defender(state, player, acting_vampire_id):
        return []
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    amount_box = context["amount"]
    book = bleed_bookkeeping(context["pending"])
    used_by: set[str] = book.setdefault(USED_BY_KEY, set())

    def _make_apply(vampire: VampireInPlay, delta: int) -> Any:
        def _apply(s: GameState) -> None:
            play_from_hand(s, player, KRCG_ID)
            amount_box[0] -= delta
            used_by.add(vampire.instance_id)

        return _apply

    options: list[HookOption] = []
    for vampire in _eligible_vampires(state, player, used_by):
        options.append(
            HookOption(
                choice=Choice(
                    f"telepathic_counter:basic:{vampire.instance_id}",
                    f"Telepathic Counter [aus]: reduce bleed by 1 ({vampire.card.name})",
                ),
                apply=_make_apply(vampire, 1),
            )
        )
        if "AUS" in vampire.card.disciplines:
            options.append(
                HookOption(
                    choice=Choice(
                        f"telepathic_counter:superior:{vampire.instance_id}",
                        f"Telepathic Counter [AUS]: reduce bleed by 2 ({vampire.card.name})",
                    ),
                    apply=_make_apply(vampire, 2),
                )
            )
    return options


hooks.register(BLEED_AMOUNT_MODIFIER_HOOK, _provide_telepathic_counter)

register(
    CardRegistration(
        krcg_id=101948,
        name="Telepathic Counter",
        status=Status.IMPLEMENTED,
        hooks=(Hook.BLEED_AMOUNT_MODIFIER,),
        source=__name__,
    )
)
