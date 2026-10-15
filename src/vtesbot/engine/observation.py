"""Builds the per-player `Observation`: what a Methuselah is allowed to see (CLAUDE.md
§5 information hiding). Single place that converts `GameState` into the agent's view."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .attachments import effective_capacity

if TYPE_CHECKING:
    from .state import AllyInPlay, GameState, MasterCardInPlay, VampireInPlay


@dataclass(frozen=True)
class VampireView:
    """Public (or, for the viewer's own uncontrolled crypt, private-but-own) view of a vampire."""

    instance_id: str
    controller: str
    zone: str  # "uncontrolled" | "ready" | "torpor" | "burned" | "removed_from_game"
    locked: bool
    is_ready_unlocked: bool
    """Mirrors `VampireInPlay.is_ready_unlocked` (OQ-46): block/reaction eligibility is
    public, and `locked` alone no longer determines it since a `woken` vampire can be
    `locked=True` yet still eligible."""
    wounded: bool
    blood: int
    contested: bool
    # None for an opponent's face-down (uncontrolled) vampire: identity is hidden.
    name: str | None
    capacity: int | None


@dataclass(frozen=True)
class AllyView:
    """Public view of an ally (`AllyInPlay`): recruited face-up (§4), so identity stays
    visible even while contested (OQ-10) -- a usability marker only, no secret created."""

    instance_id: str
    controller: str
    zone: str  # "ready" | "burned" | "contested"
    locked: bool
    contested: bool
    name: str
    life: int
    strength: int
    bleed: int


@dataclass(frozen=True)
class MasterCardView:
    """Public view of a standalone Master card (`MasterCardInPlay`; OQ-23). Mirrors
    `AllyView` minus `life`/`strength`/`bleed`; played face up (§2), identity stays
    visible even while contested."""

    instance_id: str
    controller: str
    zone: str  # "in_play" | "burned" | "contested"
    locked: bool
    contested: bool
    name: str


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
    allies: tuple[AllyView, ...]
    master_cards: tuple[MasterCardView, ...]


def build_observation(state: GameState, viewer: str) -> Observation:
    """CLAUDE.md §5: hides opponent hand, library order, opponent's face-down
    uncontrolled crypt (counts only). Else (ready/torpor, removed per OQ-24, allies,
    Master cards) known face up."""
    other = [p for p in state.players if p != viewer][0]

    def vampire_view(v: VampireInPlay) -> VampireView:
        visible_identity = v.zone != "uncontrolled" or v.controller == viewer
        return VampireView(
            instance_id=v.instance_id,
            controller=v.controller,
            zone=v.zone,
            locked=v.locked,
            is_ready_unlocked=v.is_ready_unlocked,
            wounded=v.wounded,
            blood=v.blood if visible_identity else 0,
            contested=v.contested_with is not None,
            name=v.card.name if visible_identity else None,
            # Effective capacity (OQ-8, `docs/OPEN_QUESTIONS.md`): printed
            # capacity as modified by any attached card's own bonus -- see
            # `engine/attachments.py::effective_capacity`.
            capacity=effective_capacity(state, v) if visible_identity else None,
        )

    def ally_view(a: AllyInPlay) -> AllyView:
        return AllyView(
            instance_id=a.instance_id,
            controller=a.controller,
            zone=a.zone,
            locked=a.locked,
            contested=a.contested_with is not None,
            name=a.name,
            life=a.life,
            strength=a.strength,
            bleed=a.bleed,
        )

    def master_card_view(card: MasterCardInPlay) -> MasterCardView:
        return MasterCardView(
            instance_id=card.instance_id,
            controller=card.controller,
            zone=card.zone,
            locked=card.locked,
            contested=card.contested_with is not None,
            name=card.name,
        )

    viewer_state = state.players[viewer]
    other_state = state.players[other]

    vampires = tuple(
        vampire_view(v) for p in (viewer, other) for v in state.players[p].vampires.values()
    )
    allies = tuple(ally_view(a) for p in (viewer, other) for a in state.players[p].allies.values())
    master_cards = tuple(
        master_card_view(card)
        for p in (viewer, other)
        for card in state.players[p].master_cards.values()
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
        allies=allies,
        master_cards=master_cards,
    )
