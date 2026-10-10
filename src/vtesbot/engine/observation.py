"""Builds the per-player `Observation`: what a Methuselah is allowed to see.

CLAUDE.md SS5 "Information hiding: agents receive an `Observation` ... never
the raw `GameState`. A bot must not read the opponent's hand, library order
or face-down uncontrolled vampires." This module is the single place that
converts the full `GameState` into the restricted view handed to an agent.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .attachments import effective_capacity

if TYPE_CHECKING:
    from .state import AllyInPlay, GameState, VampireInPlay


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
class AllyView:
    """Public view of an ally in play (`engine/state.py::AllyInPlay`).

    Rulebook SS4 Recruit Ally (per the `vtes-rules-reference` skill condensed
    mapping): a recruited ally enters the ready region, played face-up, the
    same as a ready vampire.

    OQ-10 (`docs/OPEN_QUESTIONS.md`, resolved): a *unique* ally (e.g. 47th
    Street Royals) can become contested against a same-named opposing ally
    (`engine/allies.py::detect_contest_on_recruit`), and the unmodified
    Rulebook SS4 Advanced Rules > Contested Cards rule then applies (not
    overridden for allies by the 2P variant, whose own "Contested crypt
    cards" section is scoped to crypt cards only): "turned face down and are
    out of play" for the contest's duration -- reflected here by `zone`
    becoming `"contested"` (`AllyInPlay.zone`'s third value, alongside
    `"ready"`/`"burned"`) and the new `contested` flag.

    Unlike `VampireView`'s `visible_identity` branch (which hides an
    opponent's still-face-down, never-yet-revealed *uncontrolled* crypt
    card), `name`/`life`/`strength`/`bleed` stay visible here even while
    contested, deliberately: by construction, an ally contest can only ever
    arise the moment a *second* same-named ally is recruited, and "Recruit
    Ally" is itself played face up (`engine/allies.py::RecruitAllySpec`'s own
    docstring, Rulebook SS4 "Announce the Action": "played (face up)") --
    so both copies' identities are already mutually known to both players
    the instant the contest is created. There is no actual secret to protect
    here (unlike an uncontrolled vampire, genuinely unknown until revealed),
    so "turned face down" is a zone/usability marker, not an information-
    hiding mechanic -- no `visible_identity`-style anonymization branch is
    sourced or needed for an ally."""

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

    Allies (rules-auditor finding, `docs/OPEN_QUESTIONS.md` OQ-7): an ally
    recruited via `engine/allies.py::recruit_ally` lives in the ready region
    exactly like a ready vampire -- so both players' allies are always shown
    in full, unconditionally, same as a ready/torpor vampire. A *contested*
    ally (OQ-10, resolved) keeps its identity visible too, for a sourced
    reason distinct from the vampire case -- see `AllyView`'s own docstring.
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

    viewer_state = state.players[viewer]
    other_state = state.players[other]

    vampires = tuple(
        vampire_view(v) for p in (viewer, other) for v in state.players[p].vampires.values()
    )
    allies = tuple(ally_view(a) for p in (viewer, other) for a in state.players[p].allies.values())

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
    )
