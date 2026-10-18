"""Game state: the single source of truth, plus the `ask()` decision
gateway. Pure core (CLAUDE.md §5): no I/O, no printing, no network. All
randomness via `GameState.rng`."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .agent import Agent
from .cards import CardAttachment, CryptCard, LibraryCard
from .errors import GameOverError, IllegalChoiceError
from .format import FormatConfig
from .log import ReplayLog
from .observation import build_observation
from .rng import GameRNG

if TYPE_CHECKING:
    from .decision import Choice, Decision

Zone = str  # "uncontrolled" | "ready" | "torpor" | "burned" | "removed_from_game"


@dataclass
class VampireInPlay:
    """One controlled vampire instance (a dealt/drawn crypt card in a
    player's crypt area). `zone='removed_from_game'` (OQ-24) is distinct
    from `'burned'` since it may still be a secret, uncontrolled card."""

    instance_id: str
    card: CryptCard
    controller: str
    blood: int = 0
    zone: Zone = "uncontrolled"
    locked: bool = False
    wounded: bool = False
    contested_with: str | None = None  # instance_id of the opposing copy, if 2P-contested
    attachments: list[CardAttachment] = field(default_factory=list)
    """Cards physically on this vampire (discipline/archetype master cards,
    equipment, retainers -- CLAUDE.md §5/§6 "equipment"/"retainer" hook
    categories; see `engine/cards.py::CardAttachment`)."""
    ability_used_turn: dict[str, int] = field(default_factory=dict)
    """Generic "once per X" scratch for a printed ability capped per turn
    (Rulebook §3 wording templates); keyed by a provider-chosen string,
    storing the turn number the ability was last used on."""
    woken: bool = False
    """Transient, action-scoped eligibility override (OQ-46): while True,
    `is_ready_unlocked` reports True even though `locked` stays True.
    Cleared by `clear_woken_vampires` at every action exit."""

    qui_vive_played_since_unlock: bool = False
    """Per-vampire cap: a minion may play only one On the Qui Vive between
    unlock phases (the card's own text); cleared by `_unlock_own_vampires`
    each unlock, unlike `woken`'s per-action scope."""

    corruption_counters: dict[str, int] = field(default_factory=dict)
    """Corruption counters on this vampire, keyed by the placing Methuselah's
    `player_id` (see `engine/corruption.py`). Sergio Bueno (krcg 201662,
    `cards/sergio_bueno.py`): "Minions with 1 or more of YOUR corruption
    counters must burn 1 blood or life to attempt to block Sergio." -- the
    printed keyword is scoped to *whoever placed* the counter, not a flat
    total, so a dict keyed by placer is the correct shape even though a 2P
    duel (CLAUDE.md §3) only ever has one possible placer besides this
    vampire's own controller. Distinct from `engine/cards.py::
    CardAttachment.counters` (a generic attachment-level running count, e.g.
    Weighted Walking Stick's own ammo/Pulled Fangs' own stealth-action-burn
    tally) -- every legal-2P card printing the "corruption counter" keyword
    puts the counter on the minion itself, never on an attached card: Aniel
    (201666), Sergio Bueno (201662), The Platinum Protocol (102232);
    Revelation of Ecstasy (101624, not on the active 2P list) agrees but is
    out of scope."""

    action_card_played_turn: dict[str, int] = field(default_factory=dict)
    """Generic "same named action card at most once per turn" cap (OQ-57,
    `docs/OPEN_QUESTIONS.md`). Rulebook §4 Detailed Turn Sequence (`data/
    sources/rulebook/2026-10-09/4-detailed-turn-sequence.md:188-191`,
    verbatim): "A minion cannot play (unless cancelled) the same named
    action card more than once each turn, even if they unlock." --
    "a minion" (this vampire specifically, not every vampire its
    controller owns) is the scope: a different vampire of the same
    controller, with its own physical copy, may still play it this same
    turn. Keyed by the card's own printed `name` (not `krcg_id`: the
    rule's own wording is name-scoped, and `LibraryCard.name` is this
    project's canonical identity field for it -- `krcg` assigns one id
    per unique card name in this project's data, so the two keyings
    coincide today, but `name` is the one the rule text actually names),
    storing the turn last played; mirrors `ability_used_turn`'s own
    "store the turn, let the reader filter" shape -- no explicit
    end-of-turn clearing needed, and "even if they unlock" needs no
    special handling, since nothing here is keyed off `locked` at all.
    See `engine/phases/minion.py::action_card_already_played_this_turn`/
    `mark_action_card_played_this_turn`."""

    @property
    def is_ready_unlocked(self) -> bool:
        return self.zone == "ready" and (not self.locked or self.woken)


@dataclass
class AllyInPlay:
    """One controlled ally instance (OQ-7, Rulebook §4 Recruit Ally).
    Mirrors `VampireInPlay`'s shape; `zone` takes ready/burned/contested
    (OQ-10)."""

    instance_id: str
    krcg_id: int
    name: str
    controller: str
    life: int
    strength: int = 0
    bleed: int = 0
    zone: str = "ready"
    locked: bool = False
    contested_with: str | None = None  # instance_id of the opposing copy, if contested
    skip_next_unlock: bool = False
    """One-shot override consumed by `_unlock_own_allies` (OQ-46): On the
    Qui Vive's ally footnote skips this ally's next unlock phase,
    independent of `woken`."""

    @property
    def is_ready_unlocked(self) -> bool:
        return self.zone == "ready" and not self.locked


@dataclass
class MasterCardInPlay:
    """One controlled standalone Master card in play (OQ-23): kept in a
    play area, not attached/resolved once. Mirrors AllyInPlay minus
    life/strength/bleed; Unique cards get Contested tracking (OQ-10/22)."""

    instance_id: str
    krcg_id: int
    name: str
    controller: str
    zone: str = "in_play"
    locked: bool = False
    contested_with: str | None = None  # instance_id of the opposing copy, if contested

    @property
    def is_unlocked_in_play(self) -> bool:
        return self.zone == "in_play" and not self.locked


@dataclass
class TurnCardInPlay:
    """One non-unique library card put into play until end of turn or
    burned (OQ-34, e.g. Loup). Distinct from `MasterCardInPlay` (OQ-23):
    self-destructs by turn end, never Unique, no contest tracking."""

    instance_id: str
    krcg_id: int
    name: str
    controller: str
    zone: str = "in_play"

    @property
    def is_in_play(self) -> bool:
        return self.zone == "in_play"


@dataclass(frozen=True)
class EnterCombatGrant:
    """One player-scoped grant letting some vampire the receiving player
    controls, with no card played, enter combat with `target_vampire_id`
    (controlled by `target_player`) as a Ⓓ action, for the rest of the turn
    it was granted on (e.g. a crypt card's own printed master-phase
    ability, such as Lucinde, Alastor: "Camarilla vampires you control can
    enter combat with the chosen vampire as a Ⓓ action"). Which of the
    receiving player's vampires may actually use a given grant (a clan/sect
    gate, say) is left to the card-specific `ACTION_CARD_PLAY_HOOK`
    provider that reads it (mirrors `cards/line_brawl.py`'s own "Requires
    an Anarch" gate) -- this dataclass only records *who the fixed target
    is* and *when the grant was made*.

    `granted_turn` is compared against `GameState.turn_number` by a reader
    (`engine/phases/minion.py::active_enter_combat_grants`), the same
    "store the turn, let the reader filter" shape `PlayerState.
    card_played_turn` already uses -- no explicit end-of-turn clearing is
    needed, unlike `TurnCardInPlay`'s zone-based self-destruct (OQ-34),
    since this is plain data, not a card occupying a zone."""

    target_player: str
    target_vampire_id: str
    granted_turn: int


@dataclass
class PlayerState:
    player_id: str
    pool: int = 0
    hand: list[LibraryCard] = field(default_factory=list)
    library: list[LibraryCard] = field(default_factory=list)
    ash_heap: list[LibraryCard] = field(default_factory=list)
    crypt_deck: list[CryptCard] = field(default_factory=list)
    vampires: dict[str, VampireInPlay] = field(default_factory=dict)
    allies: dict[str, AllyInPlay] = field(default_factory=dict)
    master_cards: dict[str, MasterCardInPlay] = field(default_factory=dict)
    turn_cards: dict[str, TurnCardInPlay] = field(default_factory=dict)
    """OQ-34 (`docs/OPEN_QUESTIONS.md`): every `TurnCardInPlay` this player
    controls, keyed by `instance_id` -- mirrors `master_cards`'s own shape."""
    card_played_turn: dict[int, int] = field(default_factory=dict)
    """Generic "only one X per turn" scratch keyed by `krcg_id`, storing
    the turn last played (e.g. Loup's "Only one Loup can be played each
    turn"); scoped to the controller, not one vampire. Distinct from
    `VampireInPlay.action_card_played_turn` (OQ-57, `docs/
    OPEN_QUESTIONS.md`): this field backs a *specific card's own printed*
    per-turn cap (an Action Modifier, not subject to the generic
    per-minion Action-card rule, which is scoped to one minion, not the
    whole controller -- see that field's own docstring), keyed by
    `krcg_id` since that card's own text never needs the "same named"
    reach the generic rule does."""
    enter_combat_grants: list[EnterCombatGrant] = field(default_factory=list)
    """Every `EnterCombatGrant` ever made to this player, across the whole
    game; a reader filters by `granted_turn == GameState.turn_number`
    rather than this list being cleared each turn -- see `EnterCombatGrant`'s
    own docstring. Bounded by the number of activations in a game (at most
    a handful per turn), not by turn count."""
    _next_instance_seq: int = 0
    _next_ally_instance_seq: int = 0
    _next_attachment_instance_seq: int = 0
    _next_master_card_instance_seq: int = 0
    _next_turn_card_instance_seq: int = 0

    def new_instance_id(self) -> str:
        self._next_instance_seq += 1
        return f"{self.player_id}-V{self._next_instance_seq}"

    def new_ally_instance_id(self) -> str:
        """Mints an ally instance id in its own namespace, distinct from a
        vampire's `"...-V<n>"` ids (OQ-7, `docs/OPEN_QUESTIONS.md`;
        `engine/allies.py::recruit_ally`)."""
        self._next_ally_instance_seq += 1
        return f"{self.player_id}-A{self._next_ally_instance_seq}"

    def new_attachment_instance_id(self) -> str:
        """Mints a card-attachment instance id in its own namespace,
        distinct from a vampire's/ally's ids (OQ-22)."""
        self._next_attachment_instance_seq += 1
        return f"{self.player_id}-AT{self._next_attachment_instance_seq}"

    def new_master_card_instance_id(self) -> str:
        """Mints a standalone master-card instance id in its own
        namespace, distinct from every other card category's (OQ-23)."""
        self._next_master_card_instance_seq += 1
        return f"{self.player_id}-M{self._next_master_card_instance_seq}"

    def new_turn_card_instance_id(self) -> str:
        """Mints a turn-scoped card instance id in its own namespace,
        distinct from every other card category's own (OQ-34, `docs/
        OPEN_QUESTIONS.md`; `engine/turn_cards.py::
        bring_turn_card_into_play`)."""
        self._next_turn_card_instance_seq += 1
        return f"{self.player_id}-T{self._next_turn_card_instance_seq}"


@dataclass
class GameState:
    format: FormatConfig
    rng: GameRNG
    log: ReplayLog
    agents: dict[str, Agent]
    players: dict[str, PlayerState]
    turn_order: list[str]
    active_player: str
    phase: str = "setup"
    turn_number: int = 1
    edge_holder: str | None = None
    first_influence_phase_used: bool = False
    eliminated: set[str] = field(default_factory=set)
    victory_points: dict[str, float] = field(default_factory=dict)
    game_over: bool = False
    winner: str | None = None
    oust_deferral_depth: int = 0
    pending_ousts: list[str] = field(default_factory=list)
    """OQ-44: while `oust_deferral_depth > 0` (`engine/pool.py::
    simultaneous_pool_losses`) `check_oust` only queues the player here; the
    queue is resolved once, together, when the outermost deferral exits."""
    combat_range: str | None = None
    """Current combat round's range, set by `combat.py`'s Determine Range
    step (Rulebook §4); None when no combat is in progress. Exposed for a
    future range-gated effect."""

    def other_player(self, player: str) -> str:
        """2P structural fact (Rulebook §5; CLAUDE.md §3): with exactly two
        Methuselahs, the sole opponent is always both prey and predator."""
        others = [p for p in self.turn_order if p != player]
        return others[0]

    def ask(self, decision: Decision) -> Choice:
        """The single gateway between the engine and a player's agent:
        builds the `Observation`, calls `Agent.decide`, enforces the
        returned `Choice` is legal. Raises `GameOverError` after `game_over`."""
        if self.game_over:
            raise GameOverError(
                f"decision {decision.kind!r} for {decision.player} requested after game over"
            )
        observation = build_observation(self, decision.player)
        agent = self.agents[decision.player]
        answer = agent.decide(observation, decision)
        legal = {c.value: c for c in decision.choices}
        if answer.value not in legal:
            raise IllegalChoiceError(
                f"{decision.player} chose {answer.value!r} for decision kind "
                f"{decision.kind!r}; legal choices were {sorted(legal)}"
            )
        canonical = legal[answer.value]
        self.log.record_decision(decision, canonical)
        return canonical

    def ask_unless_forced(self, decision: Decision) -> Choice:
        """`ask`, except a lone legal choice is taken without a `Decision`
        (decision.py: "only when needed"; no agent call). The taken choice is
        logged as a `"forced"` entry (engine/log.py), not a `"decision"`."""
        if len(decision.choices) == 1:
            self.log.record_forced(decision, decision.choices[0])
            return decision.choices[0]
        return self.ask(decision)

    def ready_unlocked_vampires(self, player: str) -> list[VampireInPlay]:
        return [v for v in self.players[player].vampires.values() if v.is_ready_unlocked]

    def is_eliminated(self, player: str) -> bool:
        return player in self.eliminated
