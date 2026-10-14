"""Turn-scoped library cards in play (OQ-34, `docs/OPEN_QUESTIONS.md`): a
non-unique card that stays in play, mutable, for the rest of the turn it was
played, auto-burned by the generic end-of-turn sweep below if nothing more
specific burns it first.

First-needed example: Loup (krcg id 102273, `types == ["Action Modifier"]`,
`clans == ["Toreador"]`, fetched via the installed `krcg` package): "Only one
Loup can be played each turn. Put this card in play. Toreador get +1
stealth. Burn this card at the end of the turn or after a Toreador performs
a successful action." Ruling on file: "Can be used even if the stealth is
not currently needed. [LSJ 20011214-2]."

This module (and `engine/state.py::TurnCardInPlay`, which it builds on)
provides only the generic "bring into play" / "is one in play" / "burn"
primitives this card shape needs, mirroring the established "entity +
module" pattern (`engine/allies.py`, `engine/attachments.py`, `engine/
master_cards.py`) a fourth time -- not a Loup-specific module: a future
`src/vtesbot/cards/loup.py` is responsible for its own eligibility checks
(including the printed "only one Loup can be played each turn" cap, a
provider-side play-offer decision deliberately not modeled here -- see
`TurnCardInPlay`'s own docstring) and for actually registering against
`STEALTH_MODIFIER_HOOK` (`engine/action.py`) to grant "+1 stealth" to the
controller's own Toreador while an instance of this is `is_in_play`.

Burn condition 2 ("after a Toreador performs a successful action") is wired
by a future card module registering a `hooks.run_effects` provider against
`ACTION_SUCCEEDED_HOOK` (`engine/action.py`, OQ-34) that checks the acting
vampire's own `card.clan` and this module's `active_turn_cards`, then calls
`burn_turn_card` -- not built here, since that check is Loup-specific (which
krcg id, which clan) and the engine stays card-agnostic (CLAUDE.md SS6).
"""

from typing import TYPE_CHECKING

from .state import TurnCardInPlay

if TYPE_CHECKING:
    from .state import GameState


def bring_turn_card_into_play(
    state: GameState,
    player: str,
    *,
    krcg_id: int,
    name: str,
) -> TurnCardInPlay:
    """Put a new turn-scoped card into play under `player`'s control."""
    p = state.players[player]
    instance_id = p.new_turn_card_instance_id()
    card = TurnCardInPlay(instance_id=instance_id, krcg_id=krcg_id, name=name, controller=player)
    p.turn_cards[instance_id] = card
    return card


def burn_turn_card(card: TurnCardInPlay) -> None:
    """Burn condition 1 or 2 (module docstring): plain mandatory zone flip,
    no cost, no decision -- either burn trigger named on the card is a
    forced effect with no legal alternative (CLAUDE.md rule 3)."""
    card.zone = "burned"


def active_turn_cards(state: GameState, player: str, krcg_id: int) -> list[TurnCardInPlay]:
    """Every `is_in_play` turn card of `krcg_id` currently controlled by
    `player` -- the "is Loup currently in play for this player" check a
    future `STEALTH_MODIFIER_HOOK`/`ACTION_SUCCEEDED_HOOK` provider needs
    (module docstring)."""
    return [
        card
        for card in state.players[player].turn_cards.values()
        if card.krcg_id == krcg_id and card.is_in_play
    ]


def clear_turn_cards_at_end_of_turn(state: GameState, player: str) -> None:
    """Burn condition 1 (module docstring): every `is_in_play` turn card
    `player` controls is burned once their own turn ends, with no decision
    offered (CLAUDE.md rule 3's mandatory-effects exception -- this is not a
    choice, every known printed instance of this card shape says "burn...
    at the end of the turn" unconditionally).

    "The turn" always means the turn in progress when the card was played
    (OQ-34, `docs/OPEN_QUESTIONS.md`): VTES turns are strictly sequential,
    never overlapping, so at any moment there is only ever one turn "in
    progress" to refer to -- and every card sharing this shape so far
    (Loup) can only ever be played by its own controller's own acting
    minion, during that controller's own minion phase, so "the turn" and
    "the controller's own turn" coincide by construction; there is no
    second reading to disambiguate. Called from `engine/phases/turn.py::
    play_turn`, for the turn's own active player, right before the turn
    flips -- the natural, and only, point "the end of the turn" can mean.
    """
    for card in state.players[player].turn_cards.values():
        if card.is_in_play:
            burn_turn_card(card)
