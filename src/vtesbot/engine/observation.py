"""Builds the per-player `Observation`: what a Methuselah is allowed to see (CLAUDE.md
§5 information hiding). Single place that converts `GameState` into the agent's view."""

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .attachments import effective_capacity, iter_attachments

if TYPE_CHECKING:
    from .cards import CardAttachment
    from .state import AllyInPlay, GameState, MasterCardInPlay, VampireInPlay


@dataclass(frozen=True)
class AttachmentView:
    """Public view of one live (`zone == "attached"`) `CardAttachment` on a vampire
    (ENG-038): attachments are always shown face up once played
    (Rulebook §3 "Playing a Card": "showing the card"), so this view carries no
    hidden-identity gate of its own -- `VampireView.attachments` below still inherits the
    host's own `visible_identity` gate, defensively: no attach mechanism in this project
    ever targets a face-down uncontrolled vampire. A burned or contested copy is left out:
    `CardAttachment.zone` lifecycle bookkeeping is engine-internal (several call sites
    never remove a burned entry from `VampireInPlay.attachments`, by design -- e.g.
    `engine/phases/minion.py::build_attachment_removal_action_spec`), not itself
    agent-relevant history, and a contested attachment provides no effect while contested
    (Rulebook §4 "Contested Cards": "turned face down and are out of play")."""

    instance_id: str
    krcg_id: int
    name: str
    controller: str | None
    counters: int | None
    is_equipment: bool


@dataclass(frozen=True)
class VampireView:
    """Public (or, for the viewer's own uncontrolled crypt, private-but-own) view of a vampire."""

    instance_id: str
    controller: str
    zone: str  # "uncontrolled" | "ready" | "torpor" | "burned" | "removed_from_game"
    locked: bool
    is_ready_unlocked: bool
    """Mirrors `VampireInPlay.is_ready_unlocked` (ENG-028): block/reaction eligibility is
    public, and `locked` alone no longer determines it since a `woken` vampire can be
    `locked=True` yet still eligible."""
    wounded: bool
    blood: int
    contested: bool
    # None for an opponent's face-down (uncontrolled) vampire: identity is hidden.
    name: str | None
    capacity: int | None
    attachments: tuple[AttachmentView, ...]
    """ENG-038: every live `CardAttachment` currently on this
    vampire (`AttachmentView`'s own docstring). Empty, not merely absent, for a face-down
    uncontrolled vampire -- see `visible_identity`'s own gate below."""
    corruption_counters: dict[str, int]
    """Per-placer corruption counter tally (`VampireInPlay.corruption_counters`,
    `engine/corruption.py`): public information once a vampire is in play -- a counter is
    always placed by a visible card effect both players witness, so no hidden-identity gate
    beyond the host's own `visible_identity` applies (mirrors `attachments` above). A copy,
    not the live dict, so a reader can never mutate engine state through it. Needed by a
    defending Methuselah's own agent to see Sergio Bueno's (krcg 201662) block-eligibility
    gate coming before choosing a block candidate. Empty for a face-down uncontrolled
    vampire, same as `attachments`."""


@dataclass(frozen=True)
class AllyView:
    """Public view of an ally (`AllyInPlay`): recruited face-up (§4), so identity stays
    visible even while contested (ENG-004) -- a usability marker only, no secret created."""

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
    """Public view of a standalone Master card (`MasterCardInPlay`; ENG-015). Mirrors
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


def _attachment_view(a: CardAttachment) -> AttachmentView:
    return AttachmentView(
        instance_id=a.instance_id,
        krcg_id=a.krcg_id,
        name=a.name,
        controller=a.controller,
        counters=a.counters,
        is_equipment=a.is_equipment,
    )


def _live_attachment_counts_by_controller(state: GameState) -> dict[str, Counter[int]]:
    """How many live (`zone == "attached"`) copies of each `krcg_id` each controller
    currently has in play, across every vampire -- feeds `_visible_ash_heap` below
    (ENG-038): a played attachment card's physical copy already sits in its player's own
    `ash_heap` (`cards/_shared.py::play_from_hand`), unconditionally, the instant it is
    played; nothing removes that entry once the same card also becomes a live
    `CardAttachment` (a separate object, built by `engine/attachments.py::attach_card`,
    with no back-reference to the `LibraryCard` `play_from_hand` moved)."""
    counts: dict[str, Counter[int]] = {}
    for _host, attachment in iter_attachments(state):
        if attachment.zone != "attached" or attachment.controller is None:
            continue
        counts.setdefault(attachment.controller, Counter())[attachment.krcg_id] += 1
    return counts


def _visible_ash_heap(
    state: GameState, player: str, live_attachment_counts: dict[str, Counter[int]]
) -> tuple[str, ...]:
    """`player`'s own ash heap, names only, minus up to one entry per currently-live
    attachment of the same `krcg_id` (ENG-038, `_live_attachment_counts_by_controller`'s
    own docstring) -- least-invasive fix: `ash_heap` is display-only (never read for
    rules logic, `build_observation`'s own module docstring), so filtering it here, by
    count rather than by identity (no instance-level link exists between a `LibraryCard`
    in `ash_heap` and the `CardAttachment` it became), needs no change to any card
    module's own `play_from_hand`/`attach_card` call sites."""
    remaining = Counter(live_attachment_counts.get(player, {}))
    names: list[str] = []
    for card in state.players[player].ash_heap:
        if remaining.get(card.krcg_id, 0) > 0:
            remaining[card.krcg_id] -= 1
            continue
        names.append(card.name)
    return tuple(names)


def build_observation(state: GameState, viewer: str) -> Observation:
    """CLAUDE.md §5: hides opponent hand, library order, opponent's face-down
    uncontrolled crypt (counts only). Else (ready/torpor, removed per ENG-016, allies,
    Master cards) known face up."""
    other = [p for p in state.players if p != viewer][0]
    live_attachment_counts = _live_attachment_counts_by_controller(state)

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
            # Effective capacity (ENG-002): printed
            # capacity as modified by any attached card's own bonus -- see
            # `engine/attachments.py::effective_capacity`.
            capacity=effective_capacity(state, v) if visible_identity else None,
            attachments=(
                tuple(_attachment_view(a) for a in v.attachments if a.zone == "attached")
                if visible_identity
                else ()
            ),
            corruption_counters=dict(v.corruption_counters) if visible_identity else {},
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
        ash_heap={p: _visible_ash_heap(state, p, live_attachment_counts) for p in state.players},
        vampires=vampires,
        allies=allies,
        master_cards=master_cards,
    )
