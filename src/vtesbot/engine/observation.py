"""Builds the per-player `Observation`: what a Methuselah is allowed to see.

CLAUDE.md SS5 "Information hiding: agents receive an `Observation` ... never
the raw `GameState`. A bot must not read the opponent's hand, library order
or face-down uncontrolled vampires." This module is the single place that
converts the full `GameState` into the restricted view handed to an agent.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay


@dataclass(frozen=True)
class VampireView:
    """Public (or, for the viewer's own uncontrolled crypt, private-but-own) view of a vampire."""

    instance_id: str
    controller: str
    zone: str  # "uncontrolled" | "ready" | "torpor" | "burned"
    locked: bool
    wounded: bool
    blood: int
    contested: bool
    # None for an opponent's face-down (uncontrolled) vampire: identity is hidden.
    name: str | None
    capacity: int | None


@dataclass(frozen=True)
class Observation:
    """What one Methuselah (`viewer`) is allowed to know about the game right now."""

    viewer: str
    phase: str
    active_player: str
    turn_number: int
    edge_holder: str | None
    pool: dict[str, int]
    hand: tuple[str, ...]  # viewer's own hand, library card names
    opponent_hand_count: int
    own_library_count: int
    opponent_library_count: int
    own_crypt_deck_count: int
    opponent_crypt_deck_count: int
    ash_heap: dict[str, tuple[str, ...]]
    vampires: tuple[VampireView, ...]


def build_observation(state: GameState, viewer: str) -> Observation:
    """CLAUDE.md SS5 information hiding.

    Hidden from `viewer`: the opponent's hand contents (only a count is
    shown), both players' library order (only counts are shown -- nobody,
    not even a Methuselah about their own deck, knows the remaining shuffled
    order), and the identity of the *opponent's* face-down uncontrolled crypt
    cards (only a count is shown; the viewer's own uncontrolled crypt cards
    are their private information and so are shown in full). Ready and
    torpor vampires are public knowledge for both players (Rulebook: the
    ready/torpor region is played face-up), so they are always shown in full.
    """
    other = [p for p in state.players if p != viewer][0]

    def vampire_view(v: VampireInPlay) -> VampireView:
        visible_identity = v.zone != "uncontrolled" or v.controller == viewer
        return VampireView(
            instance_id=v.instance_id,
            controller=v.controller,
            zone=v.zone,
            locked=v.locked,
            wounded=v.wounded,
            blood=v.blood if visible_identity else 0,
            contested=v.contested_with is not None,
            name=v.card.name if visible_identity else None,
            capacity=v.card.capacity if visible_identity else None,
        )

    viewer_state = state.players[viewer]
    other_state = state.players[other]

    vampires = tuple(
        vampire_view(v) for p in (viewer, other) for v in state.players[p].vampires.values()
    )

    return Observation(
        viewer=viewer,
        phase=state.phase,
        active_player=state.active_player,
        turn_number=state.turn_number,
        edge_holder=state.edge_holder,
        pool={p: s.pool for p, s in state.players.items()},
        hand=tuple(c.name for c in viewer_state.hand),
        opponent_hand_count=len(other_state.hand),
        own_library_count=len(viewer_state.library),
        opponent_library_count=len(other_state.library),
        own_crypt_deck_count=len(viewer_state.crypt_deck),
        opponent_crypt_deck_count=len(other_state.crypt_deck),
        ash_heap={p: tuple(c.name for c in s.ash_heap) for p, s in state.players.items()},
        vampires=vampires,
    )
