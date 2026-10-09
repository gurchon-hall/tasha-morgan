"""Game setup: 2P variant SS3.

"30 pool each; blood bank unlimited; the Edge starts uncontrolled. Shuffle
crypt and library; predator cuts. Draw 7 library cards; deal 4 crypt cards
face down to the uncontrolled region."
"""

from helpers import ScriptedAgent
from vtesbot.engine import CryptCard, FormatConfig, LibraryCard
from vtesbot.engine.setup import DeckSpec, setup_game


def _deck(prefix: str, crypt_count: int = 12, library_count: int = 40) -> DeckSpec:
    crypt = [
        CryptCard(krcg_id=i, name=f"{prefix}-crypt-{i}", capacity=3, group=5)
        for i in range(crypt_count)
    ]
    library = [
        LibraryCard(krcg_id=1000 + i, name=f"{prefix}-lib-{i}", card_type="master")
        for i in range(library_count)
    ]
    return DeckSpec(crypt=crypt, library=library)


def test_setup_deals_starting_resources():
    """2P variant SS3: 30 pool, 7-card hand, 4 uncontrolled crypt cards, Edge uncontrolled."""
    decks = {"P1": _deck("P1"), "P2": _deck("P2")}
    agents = {"P1": ScriptedAgent("P1"), "P2": ScriptedAgent("P2")}

    state = setup_game(
        decks, agents, turn_order=["P1", "P2"], seed=42, format_config=FormatConfig()
    )

    for player_id in ("P1", "P2"):
        p = state.players[player_id]
        assert p.pool == 30
        assert len(p.hand) == 7
        uncontrolled = [v for v in p.vampires.values() if v.zone == "uncontrolled"]
        assert len(uncontrolled) == 4
        assert len(p.library) == 40 - 7
        assert len(p.crypt_deck) == 12 - 4

    assert state.edge_holder is None


def test_setup_is_deterministic_for_a_given_seed():
    """CLAUDE.md determinism invariant: same seed + same decks => same resulting order."""
    decks_a = {"P1": _deck("P1"), "P2": _deck("P2")}
    decks_b = {"P1": _deck("P1"), "P2": _deck("P2")}
    agents = lambda: {"P1": ScriptedAgent("P1"), "P2": ScriptedAgent("P2")}  # noqa: E731

    state_a = setup_game(decks_a, agents(), turn_order=["P1", "P2"], seed=7)
    state_b = setup_game(decks_b, agents(), turn_order=["P1", "P2"], seed=7)

    for player_id in ("P1", "P2"):
        names_a = [c.name for c in state_a.players[player_id].library]
        names_b = [c.name for c in state_b.players[player_id].library]
        assert names_a == names_b
        hand_a = [c.name for c in state_a.players[player_id].hand]
        hand_b = [c.name for c in state_b.players[player_id].hand]
        assert hand_a == hand_b
