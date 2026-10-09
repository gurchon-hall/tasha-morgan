"""Test helpers: `ScenarioBuilder` and `ScriptedAgent`.

Per the `rules-scenario-test` skill: build a precise game state directly
(not by playing through a real deck), script the exact decisions expected,
and fail loudly if the engine asks something unscripted or offers an
illegal choice, or if the script has leftover unused answers.
"""

from dataclasses import dataclass

from vtesbot.engine import (
    Choice,
    CryptCard,
    Decision,
    FormatConfig,
    GameRNG,
    GameState,
    LibraryCard,
    Observation,
    PlayerState,
    ReplayLog,
    VampireInPlay,
)
from vtesbot.engine.damage import apply_damage as _apply_damage


@dataclass
class ScriptedAnswer:
    kind: str
    value: str


class UnexpectedDecisionError(AssertionError):
    pass


class ScriptedAgent:
    """Answers decisions from a pre-set script; fails loudly on any mismatch."""

    def __init__(self, player_id: str, answers: list[ScriptedAnswer] | None = None) -> None:
        self.player_id = player_id
        self._answers: list[ScriptedAnswer] = list(answers or [])
        self._pos = 0

    def expect(self, kind: str, value: str) -> ScriptedAgent:
        self._answers.append(ScriptedAnswer(kind, value))
        return self

    def decide(self, observation: Observation, decision: Decision) -> Choice:
        if self._pos >= len(self._answers):
            raise UnexpectedDecisionError(
                f"{self.player_id}: unexpected decision kind={decision.kind!r} "
                f"choices={[c.value for c in decision.choices]} (script exhausted)"
            )
        expected = self._answers[self._pos]
        self._pos += 1
        if expected.kind != decision.kind:
            raise UnexpectedDecisionError(
                f"{self.player_id}: expected decision kind {expected.kind!r}, got {decision.kind!r}"
            )
        matching = [c for c in decision.choices if c.value == expected.value]
        if not matching:
            raise AssertionError(
                f"{self.player_id}: scripted choice {expected.value!r} not among offered "
                f"choices {[c.value for c in decision.choices]} for kind {decision.kind!r}"
            )
        return matching[0]

    def assert_exhausted(self) -> None:
        remaining = len(self._answers) - self._pos
        assert remaining == 0, f"{self.player_id}: {remaining} unused scripted answer(s) remain"


class ScenarioAgent(ScriptedAgent):
    """Alias kept for readability in tests that script one agent per player."""


_CRYPT_SEQ = 0
_LIB_SEQ = 0


def _next_crypt_id() -> int:
    global _CRYPT_SEQ
    _CRYPT_SEQ += 1
    return 900_000 + _CRYPT_SEQ


def _next_lib_id() -> int:
    global _LIB_SEQ
    _LIB_SEQ += 1
    return 800_000 + _LIB_SEQ


class _PlayerBuilder:
    def __init__(self, builder: ScenarioBuilder, player_id: str, pool: int) -> None:
        self._builder = builder
        self.player_id = player_id
        self.pool = pool
        self.hand: list[LibraryCard] = []
        self.library: list[LibraryCard] = []
        self.crypt_deck: list[CryptCard] = []
        self.ash_heap: list[LibraryCard] = []
        self.vampires: list[VampireInPlay] = []
        self._seq = 0

    def _instance_id(self, label: str | None) -> str:
        self._seq += 1
        return label or f"{self.player_id}-V{self._seq}"

    def ready_vampire(
        self,
        label: str | None = None,
        *,
        capacity: int = 3,
        blood: int = 0,
        wounded: bool = False,
        locked: bool = False,
        name: str | None = None,
    ) -> _PlayerBuilder:
        instance_id = self._instance_id(label)
        card = CryptCard(
            krcg_id=_next_crypt_id(), name=name or instance_id, capacity=capacity, group=5
        )
        self.vampires.append(
            VampireInPlay(
                instance_id=instance_id,
                card=card,
                controller=self.player_id,
                blood=blood,
                zone="ready",
                locked=locked,
                wounded=wounded,
            )
        )
        return self

    def torpid_vampire(
        self, label: str | None = None, *, capacity: int = 3, blood: int = 0
    ) -> _PlayerBuilder:
        instance_id = self._instance_id(label)
        card = CryptCard(krcg_id=_next_crypt_id(), name=instance_id, capacity=capacity, group=5)
        self.vampires.append(
            VampireInPlay(
                instance_id=instance_id,
                card=card,
                controller=self.player_id,
                blood=blood,
                zone="torpor",
            )
        )
        return self

    def uncontrolled_vampire(
        self,
        label: str | None = None,
        *,
        capacity: int = 3,
        blood: int = 0,
        name: str | None = None,
    ) -> _PlayerBuilder:
        instance_id = self._instance_id(label)
        card = CryptCard(
            krcg_id=_next_crypt_id(), name=name or instance_id, capacity=capacity, group=5
        )
        self.vampires.append(
            VampireInPlay(
                instance_id=instance_id,
                card=card,
                controller=self.player_id,
                blood=blood,
                zone="uncontrolled",
            )
        )
        return self

    def crypt_deck_cards(
        self, *, count: int, capacity: int = 3, name_prefix: str = "crypt"
    ) -> _PlayerBuilder:
        for i in range(count):
            self.crypt_deck.append(
                CryptCard(
                    krcg_id=_next_crypt_id(), name=f"{name_prefix}-{i}", capacity=capacity, group=5
                )
            )
        return self

    def hand_cards(self, names: list[str], card_type: str = "master") -> _PlayerBuilder:
        for name in names:
            self.hand.append(LibraryCard(krcg_id=_next_lib_id(), name=name, card_type=card_type))
        return self

    def library_cards(self, names: list[str], card_type: str = "master") -> _PlayerBuilder:
        for name in names:
            self.library.append(LibraryCard(krcg_id=_next_lib_id(), name=name, card_type=card_type))
        return self

    def player(self, player_id: str, pool: int = 30) -> _PlayerBuilder:
        return self._builder.player(player_id, pool)

    def build(self, agents: dict[str, object] | None = None) -> ScenarioGame:
        return self._builder.build(agents)


class ScenarioBuilder:
    """Fluent builder for a precise `GameState`, bypassing real deck shuffling/setup."""

    def __init__(
        self, seed: int = 1, format: str = "2p", first_influence_phase_used: bool = True
    ) -> None:
        self.seed = seed
        self.format_config = FormatConfig(two_player=(format == "2p"))
        self.first_influence_phase_used = first_influence_phase_used
        self._players: dict[str, _PlayerBuilder] = {}
        self._turn_order: list[str] = []
        self._edge_holder: str | None = None

    def player(self, player_id: str, pool: int = 30) -> _PlayerBuilder:
        pb = _PlayerBuilder(self, player_id, pool)
        self._players[player_id] = pb
        self._turn_order.append(player_id)
        return pb

    def edge_holder(self, player_id: str | None) -> ScenarioBuilder:
        self._edge_holder = player_id
        return self

    def build(self, agents: dict[str, object] | None = None) -> ScenarioGame:
        if len(self._turn_order) != 2:
            raise ValueError("ScenarioBuilder requires exactly two players")
        log = ReplayLog()
        rng = GameRNG(seed=self.seed, log=log)
        agents = agents or {p: ScriptedAgent(p) for p in self._turn_order}

        players: dict[str, PlayerState] = {}
        for player_id, pb in self._players.items():
            ps = PlayerState(player_id=player_id, pool=pb.pool)
            ps.hand = list(pb.hand)
            ps.library = list(pb.library)
            ps.crypt_deck = list(pb.crypt_deck)
            ps.ash_heap = list(pb.ash_heap)
            for v in pb.vampires:
                ps.vampires[v.instance_id] = v
            players[player_id] = ps

        state = GameState(
            format=self.format_config,
            rng=rng,
            log=log,
            agents=agents,
            players=players,
            turn_order=list(self._turn_order),
            active_player=self._turn_order[0],
            phase="minion",
            edge_holder=self._edge_holder,
            first_influence_phase_used=self.first_influence_phase_used,
        )
        for p in self._turn_order:
            state.victory_points[p] = 0
        return ScenarioGame(state)


@dataclass
class ScenarioGame:
    """Thin convenience wrapper over a built `GameState` for scenario tests."""

    state: GameState

    def vampire(self, instance_id: str) -> VampireInPlay:
        for ps in self.state.players.values():
            if instance_id in ps.vampires:
                return ps.vampires[instance_id]
        raise KeyError(instance_id)

    def zone_of(self, instance_id: str) -> str:
        return self.vampire(instance_id).zone

    def blood_of(self, instance_id: str) -> int:
        return self.vampire(instance_id).blood

    def pool_of(self, player_id: str) -> int:
        return self.state.players[player_id].pool

    def apply_damage(
        self, target: str, normal: int = 0, aggravated: int = 0, source: object = None
    ) -> None:
        vampire = self.vampire(target)
        _apply_damage(self.state, vampire.controller, vampire, normal=normal, aggravated=aggravated)
