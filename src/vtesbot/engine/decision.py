"""Decision points: the engine's mechanism for never choosing on behalf of a player.

CLAUDE.md SS5 engine invariant: "whenever any player may act ... the engine
yields a `Decision` with the full list of legal choices. Agents only ever
pick from that list." This module defines the data shapes; `GameState.ask`
(see `engine/state.py`) is the single place that calls an agent and enforces
that its answer is one of `decision.choices`.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Choice:
    """One legal, selectable option within a `Decision`.

    `value` is the machine-readable id an agent returns (e.g. "hand_strike",
    "block_with:P2-V1", "decline"); `label` is a human-readable description
    for logs/CLI.
    """

    value: str
    label: str

    def __hash__(self) -> int:  # noqa: D105 - identity by value only
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Choice):
            return self.value == other.value
        return NotImplemented


@dataclass(frozen=True)
class Decision:
    """A single point where exactly one player must choose among legal options.

    `kind` names the rule mechanism (e.g. "block_attempt", "strike_choice",
    "mend_damage", "influence_action", "press"); `context` carries extra,
    read-only information relevant to that kind (e.g. which vampire is acting)
    for logging/agent reasoning. `choices` must be non-empty; callers must
    not construct a `Decision` when there is nothing legal to add beyond a
    single default (the "only when needed" principle, Rulebook SS4 Block
    Attempts) -- such steps are resolved automatically by the engine instead.
    """

    player: str
    kind: str
    choices: tuple[Choice, ...]
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.choices:
            raise ValueError(f"Decision(kind={self.kind!r}) offered with no legal choices")
