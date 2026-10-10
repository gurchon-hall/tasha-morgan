"""Game state: the single source of truth, plus the `ask()` decision gateway.

Pure core (CLAUDE.md SS5): no I/O, no printing, no network. All randomness
goes through `GameState.rng`. `GameState.ask` is the only way engine code
may obtain a player's choice; it builds the restricted `Observation`, calls
the player's `Agent`, and rejects any answer not in `decision.choices`
(CLAUDE.md "legality by construction").
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .agent import Agent
from .cards import CardAttachment, CryptCard, LibraryCard
from .errors import IllegalChoiceError
from .format import FormatConfig
from .log import ReplayLog
from .observation import build_observation
from .rng import GameRNG

if TYPE_CHECKING:
    from .decision import Choice, Decision

Zone = str  # "uncontrolled" | "ready" | "torpor" | "burned"


@dataclass
class VampireInPlay:
    """One controlled vampire instance (a dealt/drawn crypt card in a player's crypt area)."""

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
    equipment, retainers -- CLAUDE.md SS5/SS6 "equipment"/"retainer" hook
    categories; see `engine/cards.py::CardAttachment`)."""

    @property
    def is_ready_unlocked(self) -> bool:
        return self.zone == "ready" and not self.locked


@dataclass
class AllyInPlay:
    """One controlled ally instance (OQ-7, `docs/OPEN_QUESTIONS.md`; Rulebook
    SS4 "Recruit Ally").

    Mirrors `VampireInPlay`'s shape: `zone` takes the three values
    `engine/allies.py` and `engine/phases/unlock.py` need -- `"ready"`
    (played face up, usable), `"burned"` (removed from play) and
    `"contested"` (Rulebook SS4 Advanced Rules > Contested Cards, OQ-10) --
    and `locked`/`is_ready_unlocked` follow the same "ready and not locked"
    convention as a vampire's.
    """

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

    @property
    def is_ready_unlocked(self) -> bool:
        return self.zone == "ready" and not self.locked


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
    _next_instance_seq: int = 0
    _next_ally_instance_seq: int = 0

    def new_instance_id(self) -> str:
        self._next_instance_seq += 1
        return f"{self.player_id}-V{self._next_instance_seq}"

    def new_ally_instance_id(self) -> str:
        """Mints an ally instance id in its own namespace, distinct from a
        vampire's `"...-V<n>"` ids (OQ-7, `docs/OPEN_QUESTIONS.md`;
        `engine/allies.py::recruit_ally`)."""
        self._next_ally_instance_seq += 1
        return f"{self.player_id}-A{self._next_ally_instance_seq}"


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

    def other_player(self, player: str) -> str:
        """2P structural fact (Rulebook SS5; CLAUDE.md SS3): with exactly two
        Methuselahs, the sole opponent is always both prey and predator."""
        others = [p for p in self.turn_order if p != player]
        return others[0]

    def ask(self, decision: Decision) -> Choice:
        """The single gateway between the engine and a player's agent.

        CLAUDE.md "Decision points are explicit": builds the `Observation`
        for `decision.player`, calls their `Agent.decide`, and enforces that
        the returned `Choice` is one of `decision.choices` -- never letting
        the engine or the agent silently invent an illegal option.
        """
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

    def ready_unlocked_vampires(self, player: str) -> list[VampireInPlay]:
        return [v for v in self.players[player].vampires.values() if v.is_ready_unlocked]

    def is_eliminated(self, player: str) -> bool:
        return player in self.eliminated
