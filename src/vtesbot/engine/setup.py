"""Game setup.

Source: 2P variant SS3 Game Setup (per the `vtes-rules-reference` skill
condensed mapping): "30 pool each; blood bank unlimited; the Edge starts
uncontrolled. Shuffle crypt and library; predator cuts. Draw 7 library
cards; deal 4 crypt cards face down to the uncontrolled region." Deck
construction legality (crypt >= 12, one group or two consecutive groups,
library 40-60) is checked by `scripts/validate_deck.py` / the
`deck-validation` skill before a deck reaches this function; `setup_game`
assumes it is handed an already-legal `DeckSpec`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .agent import Agent
from .cards import CryptCard, LibraryCard
from .format import FormatConfig
from .log import ReplayLog
from .rng import GameRNG
from .state import GameState, PlayerState, VampireInPlay

STARTING_POOL = 30
STARTING_HAND_SIZE = 7
STARTING_UNCONTROLLED_CRYPT = 4


@dataclass
class DeckSpec:
    """An already-expanded, already-legal decklist (one entry per physical card)."""

    crypt: list[CryptCard] = field(default_factory=list)
    library: list[LibraryCard] = field(default_factory=list)


def setup_game(
    decks: Mapping[str, DeckSpec],
    agents: Mapping[str, Agent],
    turn_order: Sequence[str],
    seed: int,
    format_config: FormatConfig | None = None,
) -> GameState:
    """Build the initial `GameState` for a 2P duel (2P variant SS3).

    `turn_order` lists the two player ids in play order; `turn_order[0]` is
    the first player (relevant to the 2P influence-phase transfer ramp,
    SS2.3, applied later in `influence_phase`).
    """
    if set(decks) != set(agents) or set(decks) != set(turn_order) or len(turn_order) != 2:
        raise ValueError(
            "setup_game requires exactly the same two player ids in decks/agents/turn_order"
        )

    format_config = format_config or FormatConfig()
    log = ReplayLog()
    rng = GameRNG(seed=seed, log=log)

    players: dict[str, PlayerState] = {}
    for player_id, deck in decks.items():
        state = PlayerState(player_id=player_id, pool=STARTING_POOL)

        library = list(deck.library)
        rng.shuffle(library, f"{player_id} shuffles library")
        crypt_deck = list(deck.crypt)
        rng.shuffle(crypt_deck, f"{player_id} shuffles crypt")

        players[player_id] = state
        state.library = library
        state.crypt_deck = crypt_deck

    # 2P variant SS3: "predator cuts". With exactly two players each is the
    # other's predator (Rulebook SS5 structural note), so the opponent cuts
    # each shuffled deck before draws are taken.
    for player_id, state in players.items():
        predator = [p for p in turn_order if p != player_id][0]
        rng.cut(state.library, f"{predator} cuts {player_id}'s library")
        rng.cut(state.crypt_deck, f"{predator} cuts {player_id}'s crypt")

    for player_id, state in players.items():
        for _ in range(STARTING_HAND_SIZE):
            state.hand.append(state.library.pop(0))
        for _ in range(STARTING_UNCONTROLLED_CRYPT):
            card = state.crypt_deck.pop(0)
            instance_id = state.new_instance_id()
            state.vampires[instance_id] = VampireInPlay(
                instance_id=instance_id, card=card, controller=player_id, zone="uncontrolled"
            )

    game = GameState(
        format=format_config,
        rng=rng,
        log=log,
        agents=dict(agents),
        players=players,
        turn_order=list(turn_order),
        active_player=turn_order[0],
        phase="setup",
    )
    for player_id in turn_order:
        game.victory_points[player_id] = 0
    return game
