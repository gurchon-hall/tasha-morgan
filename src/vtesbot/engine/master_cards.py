"""Standalone Master cards in play (OQ-23, `docs/OPEN_QUESTIONS.md`): bring
one into play, detect/resolve a Contested Cards contest against it.

Originally built (as `engine/locations.py`, `LocationInPlay`) for Oxford
University, England (krcg id 101341, "Unique location.\n You can lock this
card and burn X pool during the polling step of a political action to get
+2X votes.") on the premise that "location" needed its own engine entity. A
later sweep of the full active 2P pool corrected that premise: krcg has no
`Type.LOCATION` at all -- "Unique location." is free text on an ordinary
`Master`-type card, no different in kind from "Unique." or "Trifle." on any
other Master card. This module (and `engine/state.py::MasterCardInPlay`,
which it builds on) is deliberately named and framed generically: it backs
every standalone Master card in play, not just the four "Unique location."
ones, and not only Unique cards either -- see `MasterCardInPlay`'s own
docstring for the full "at least 18 cards share this shape" finding
(Oxford University England 101341, The Barrens 100135, Chantry 100329,
Cursed Abattoir 102313, Tension in the Ranks 101958, Wider View 102180, and
others).

Deliberately mirrors `engine/allies.py`'s own shape (itself already a
mirror of `engine/contests.py`'s crypt-card shape, generalized a third time
by `engine/attachments.py` for OQ-22) rather than reinventing a fourth
variant. This module provides only the "bring into play"/"contest"/
"resolve a contest" primitives a future card module's `"master_phase_play"`
hook provider needs (`engine/phases/master.py`, the same generic pattern
Life in the City already uses -- no engine change needed there, a
card-playing provider simply calls `vtesbot.cards._shared.play_from_hand`
then `bring_master_card_into_play`, and (only for a card printed "Unique")
`detect_contest_on_bring_into_play`, exactly as Life in the City calls
`add_blood` today).

`detect_contest_on_bring_into_play` must only ever be called for a card
whose own printed text says "Unique" -- the rulebook's Contested Cards
mechanism does not apply to a non-unique card, and two players
independently playing their own copy of the *same non-unique* Master card
(e.g. Wider View) is ordinary deck construction, never a contest. A card
module for a non-unique standalone Master card simply never calls this
function, so that instance's `contested_with` stays `None` for its whole
lifetime -- see `MasterCardInPlay`'s own docstring.

Still deliberately out of scope, because no card in the pool needs it yet:
a standalone Master card ever acting, blocking, bearing counters (Cursed
Abattoir) or being targeted by a control-transfer effect (Disputed
Territory, krcg id 100557, "Successful referendum means the chosen
Methuselah takes control of the chosen location" -- found by OQ-23's own
sweep, not built here).
"""

from typing import TYPE_CHECKING

from .decision import Choice, Decision
from .pool import lose_pool
from .state import MasterCardInPlay

if TYPE_CHECKING:
    from .state import GameState


def bring_master_card_into_play(
    state: GameState,
    player: str,
    *,
    krcg_id: int,
    name: str,
) -> MasterCardInPlay:
    """Bring a new standalone Master card into play under `player`'s control.

    Starts `zone="in_play"`, `locked=False` -- see `MasterCardInPlay`'s own
    docstring for why a freshly-played instance starts unlocked (no "enters
    locked" clause anywhere in the generic Master Phase play rule, unlike
    Recruit Ally's own specific "cannot act this turn").
    """
    p = state.players[player]
    instance_id = p.new_master_card_instance_id()
    card = MasterCardInPlay(
        instance_id=instance_id,
        krcg_id=krcg_id,
        name=name,
        controller=player,
    )
    p.master_cards[instance_id] = card
    return card


def detect_contest_on_bring_into_play(state: GameState, brought_in: MasterCardInPlay) -> None:
    """Flag `brought_in` and any same-named in-play opposing instance as
    contested, and move both out of the usable `"in_play"` zone for the
    contest's duration.

    Only call this for a card printed "Unique" -- see this module's own
    docstring for why a non-unique card (e.g. Wider View) must never call
    this at all.

    Source: Rulebook SS4 Advanced Rules > Contested Cards (quoted in full in
    `docs/OPEN_QUESTIONS.md` OQ-10/OQ-23): "If more than one unique card with
    the same name is brought into play, that means control of the card is
    being contested. For the duration of the contest, all of the contested
    cards are turned face down and are out of play." Not overridden by the
    2P variant (that override is scoped to crypt cards only -- see
    `engine/allies.py`'s own module docstring, re-confirmed by OQ-22 for an
    attached master card and here for a standalone one); matched by printed
    name (`MasterCardInPlay.name`), exactly as the rulebook's own test is
    "the same name", not the same krcg id.

    Mirrors `engine/allies.py::detect_contest_on_recruit`'s shape exactly
    (only checks the opponent, never the same player's own cards -- same
    OQ-16 scope boundary already tracked for the vampire/ally/attachment
    paths, not a new gap introduced here). Only `"in_play"` opposing
    instances can be contested against -- a `"burned"` one is gone, and with
    exactly two players (CLAUDE.md SS3) the opponent can never already have
    a `"contested"` copy of the same name waiting (that would require a
    third copy, impossible between two players at once).
    """
    opponent = state.other_player(brought_in.controller)
    for other in state.players[opponent].master_cards.values():
        if other.zone == "in_play" and other.name == brought_in.name:
            brought_in.contested_with = other.instance_id
            other.contested_with = brought_in.instance_id
            brought_in.zone = "contested"
            other.zone = "contested"
            return


def resolve_one_master_card_contest(state: GameState, player: str, card: MasterCardInPlay) -> None:
    """Rulebook SS4 Unlock Phase + Advanced Rules > Contested Cards (OQ-15's
    pay-1-pool-or-yield mechanism, generalized a third time by OQ-23): pay 1
    pool to keep contesting `card` this unlock phase, or yield (burn your
    own copy).

    Mirrors `engine/allies.py::resolve_one_ally_contest`'s two branches
    exactly, for the same reason that function differs from the crypt-card
    case: there is no 2P "stays in play and usable" override for this card
    type, so "paying" correctly leaves `card.zone == "contested"` (still out
    of play) rather than restoring it, and "yielding" burns the yielding
    card and clears the opponent's own `contested_with` immediately but
    deliberately leaves the opponent's own `zone` at `"contested"` --
    restored only on that opponent's own next unlock phase
    (`engine/phases/unlock.py::_unlock_own_master_cards`), per the
    rulebook's "unlocked and turned face up during your *next* unlock
    phase" wording.
    """
    choices = (
        Choice("pay", "Pay 1 pool to keep contesting"),
        Choice("yield", "Yield: burn this card"),
    )
    decision = Decision(
        player=player,
        kind="master_card_contest_resolution",
        choices=choices,
        context={"card": card.instance_id, "contested_with": card.contested_with},
    )
    choice = state.ask(decision)
    if choice.value == "pay":
        lose_pool(state, player, 1)
    else:
        opponent_card = _find_master_card_instance(state, card.contested_with)
        card.zone = "burned"
        card.locked = False
        if opponent_card is not None:
            # Cleared immediately (nothing contests the opponent's copy any
            # more), but its `zone` deliberately stays "contested" here --
            # see this function's own docstring and `_unlock_own_master_cards`.
            opponent_card.contested_with = None
        card.contested_with = None


def _find_master_card_instance(
    state: GameState, instance_id: str | None
) -> MasterCardInPlay | None:
    if instance_id is None:
        return None
    for player_state in state.players.values():
        if instance_id in player_state.master_cards:
            return player_state.master_cards[instance_id]
    return None
