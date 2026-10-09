"""Pure rules engine: state, phases, impulse/sequencing, actions, blocks,
combat, politics, torpor/diablerie (CLAUDE.md SS5).

No I/O, no printing, no network; all randomness via `GameState.rng`
(CLAUDE.md engine invariants).
"""

from .agent import Agent
from .cards import CryptCard, LibraryCard
from .decision import Choice, Decision
from .errors import IllegalChoiceError, UnresolvedRulingError
from .format import FormatConfig
from .log import ReplayLog
from .observation import Observation, VampireView, build_observation
from .ousting import check_oust
from .rng import GameRNG
from .setup import DeckSpec, setup_game
from .state import GameState, PlayerState, VampireInPlay

__all__ = [
    "Agent",
    "CryptCard",
    "LibraryCard",
    "Choice",
    "Decision",
    "IllegalChoiceError",
    "UnresolvedRulingError",
    "FormatConfig",
    "ReplayLog",
    "Observation",
    "VampireView",
    "build_observation",
    "check_oust",
    "GameRNG",
    "DeckSpec",
    "setup_game",
    "GameState",
    "PlayerState",
    "VampireInPlay",
]
