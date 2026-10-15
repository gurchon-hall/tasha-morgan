"""Horst von Bruhl (krcg id 201550, `src/vtesbot/cards/horst_von_bruhl.py`).

Card text: "Camarilla Prince of Mannheim." No rulings on file.

A single clause, the title itself -- same shape as Mkhokheli (201561,
`tests/cards/test_mkhokheli.py`), whose test pattern this one mirrors. One
assertion each: the registry entry, and the "Camarilla Prince of Mannheim"
title clause (already generically handled by `engine/politics.py::
TITLE_VOTES`, not this module -- proven end to end through the real
`political_action`).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.horst_von_bruhl import KRCG_ID
from vtesbot.engine import CryptCard
from vtesbot.engine.politics import political_action

NAME = "Horst von Brühl"


def _make_horst(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Horst von Bruhl's real
    printed identity (`CryptCard` is frozen)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=6,
        group=6,
        clan="Ventrue",
        title="Prince",
        disciplines=("aus", "dom", "pre", "FOR"),
    )


def test_registered_as_implemented_with_no_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.hooks == ()
    assert reg.blocked_reason is None


def test_krcg_confirms_the_title_and_no_other_clause():
    import krcg

    card = krcg.load()[KRCG_ID]
    assert card.text.strip() == "Camarilla Prince of Mannheim."
    assert card.title == "Prince"
    assert card.rulings == []


def test_a_ready_horst_contributes_2_votes_as_a_prince_title_source():
    """Rulebook §4 Politics > Gaining Votes: "2 votes for each ready prince
    or baron" -- `engine/politics.py::TITLE_VOTES["Prince"] == 2`. Proven
    here, end to end through the real `political_action`, to confirm this
    specific printed vampire's `title="Prince"` really is wired to the
    generic title-vote source exactly like any other titled vampire."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Horst1", capacity=6, blood=1)
    _make_horst(p1, "Horst1")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Horst1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Horst1"))

    assert result is True  # 1 (political action card) + 2 (Prince title) for vs 0 against
    actor.assert_exhausted()
