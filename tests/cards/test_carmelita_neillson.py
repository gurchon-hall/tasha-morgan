"""Carmelita Neillson (201625): one test per condition of "Camarilla: While
Carmelita is ready, you get +1 hand size" (sect, ready region locked or not per
RUL-019, controller only), against the real `HAND_SIZE_MODIFIER` hook."""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.carmelita_neillson import KRCG_ID
from vtesbot.engine import CryptCard, Sect
from vtesbot.engine.format import FormatConfig
from vtesbot.engine.hand import effective_hand_size, reconcile_hand_size


def _make_carmelita(
    builder_player, instance_id: str, *, sect: Sect | None = Sect.CAMARILLA
) -> None:
    """Swap the just-built vampire's `card` for Carmelita's real printed
    identity (`CryptCard` is frozen, mirrors `test_modius.py::_make_modius`'s
    own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name="Carmelita Neillson",
        capacity=5,
        group=7,
        clan="Toreador",
        disciplines=("cel", "pre", "AUS"),
        sect=sect,
    )


def test_registered_as_implemented_against_the_hand_size_modifier_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Carmelita Neillson"
    assert reg.blocked_reason is None


def test_plus_1_hand_size_while_ready_unlocked_camarilla_and_controlled():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Carmelita1", capacity=5, blood=1)
    _make_carmelita(p1, "Carmelita1")
    builder.player("P2", pool=30)
    game = builder.build()

    assert effective_hand_size(game.state, "P1") == 8


def test_bonus_while_carmelita_is_locked():
    """ "While Carmelita is ready": a locked Carmelita is still in the ready
    region, so the bonus applies (RUL-019)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Carmelita1", capacity=5, blood=1, locked=True)
    _make_carmelita(p1, "Carmelita1")
    builder.player("P2", pool=30)
    game = builder.build()

    assert effective_hand_size(game.state, "P1") == 8


def test_no_bonus_while_carmelita_is_in_torpor():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.torpid_vampire("Carmelita1", capacity=5, blood=0)
    _make_carmelita(p1, "Carmelita1")
    builder.player("P2", pool=30)
    game = builder.build()

    assert effective_hand_size(game.state, "P1") == 7


def test_no_bonus_while_carmelita_is_uncontrolled():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.uncontrolled_vampire("Carmelita1", capacity=5)
    _make_carmelita(p1, "Carmelita1")
    builder.player("P2", pool=30)
    game = builder.build()

    assert effective_hand_size(game.state, "P1") == 7


def test_no_bonus_for_a_vampire_whose_sect_is_not_camarilla():
    """ "Camarilla:" is a live condition on her own current sect, same
    convention `dust_up.py`'s "Requires an Anarch" gate already established
    -- a (synthetic, for this test) non-Camarilla Carmelita grants nothing."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Carmelita1", capacity=5, blood=1)
    _make_carmelita(p1, "Carmelita1", sect=Sect.ANARCH)
    builder.player("P2", pool=30)
    game = builder.build()

    assert effective_hand_size(game.state, "P1") == 7


def test_no_bonus_when_sect_is_not_modeled_for_this_instance():
    """`CryptCard.sect` defaults to `None` for a synthetic vampire never run
    through `derive_sect` -- treated as "does not qualify", never assumed to
    be Camarilla (CLAUDE.md "no guessing")."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Carmelita1", capacity=5, blood=1)
    _make_carmelita(p1, "Carmelita1", sect=None)
    builder.player("P2", pool=30)
    game = builder.build()

    assert effective_hand_size(game.state, "P1") == 7


def test_bonus_is_scoped_to_carmelitas_own_controller():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("Carmelita1", capacity=5, blood=1)
    _make_carmelita(p2, "Carmelita1")
    game = builder.build()

    assert effective_hand_size(game.state, "P1") == 7
    assert effective_hand_size(game.state, "P2") == 8


def test_reconcile_draws_up_immediately_when_carmelita_leaves_torpor():
    """Integration: `reconcile_hand_size` reflects the bonus the instant it
    starts applying -- her controller draws one extra card up to the new
    effective hand size of 8, no `Decision` needed (drawing up is
    automatic)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.torpid_vampire("Carmelita1", capacity=5, blood=0)
    _make_carmelita(p1, "Carmelita1")
    p1.hand_cards(["Alpha"] * 7)
    p1.library_cards(["Bonus"])
    builder.player("P2", pool=30)
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # would fail loudly if asked anything

    assert effective_hand_size(game.state, "P1") == 7  # in torpor: no bonus yet
    game.vampire("Carmelita1").zone = "ready"  # she is rescued mid-turn

    reconcile_hand_size(game.state, "P1")

    assert len(game.state.players["P1"].hand) == 8
    assert [c.name for c in game.state.players["P1"].hand].count("Bonus") == 1
    assert game.state.players["P1"].library == []


def test_reconcile_forces_an_immediate_discard_when_carmelita_enters_torpor():
    """Carmelita going to torpor mid-turn costs the +1 at once: a real discard
    `Decision` brings the hand down to 7."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Carmelita1", capacity=5, blood=1)
    _make_carmelita(p1, "Carmelita1")
    p1.hand_cards(["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"])
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1").expect("hand_size_discard", "discard:7")  # Theta
    game.state.agents["P1"] = agent

    assert effective_hand_size(game.state, "P1") == 8  # ready: +1 bonus active
    game.vampire("Carmelita1").zone = "torpor"  # she goes to torpor mid-turn

    reconcile_hand_size(game.state, "P1")

    assert len(game.state.players["P1"].hand) == 7
    assert "Theta" not in [c.name for c in game.state.players["P1"].hand]
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Theta"]
    agent.assert_exhausted()


def test_no_bonus_against_the_format_base_without_a_registered_carmelita():
    """Sanity: with no Carmelita in play at all, `effective_hand_size` stays
    at the plain `FormatConfig.hand_size` base (7) -- the bonus is never
    applied unconditionally."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    game.state.format = FormatConfig(hand_size=7)

    assert effective_hand_size(game.state, "P1") == 7
