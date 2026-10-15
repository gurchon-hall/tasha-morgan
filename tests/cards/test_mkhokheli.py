"""Mkhokheli (krcg id 201561, `src/vtesbot/cards/mkhokheli.py`).

Card text: "Camarilla Prince of Cape Town." No rulings on file.

A single clause, the title itself -- same shape as Leumeah (201526,
`tests/cards/test_leumeah.py`), whose test pattern this one mirrors. One
assertion each: the registry entry, and the "Camarilla Prince of Cape Town"
title clause (already generically handled by `engine/politics.py::
TITLE_VOTES`, not this module -- proven end to end through the real
`political_action`).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.mkhokheli import KRCG_ID
from vtesbot.engine import CryptCard
from vtesbot.engine.politics import political_action

NAME = "Mkhokheli"


def _make_mkhokheli(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Mkhokheli's real printed
    identity (`CryptCard` is frozen)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=6,
        group=6,
        clan="Toreador",
        title="Prince",
        disciplines=("aus", "cel", "for", "PRE"),
    )


def test_registered_as_implemented_with_no_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.hooks == ()
    assert reg.blocked_reason is None


def test_a_ready_mkhokheli_contributes_2_votes_as_a_prince_title_source():
    """Rulebook §4 Politics > Gaining Votes: "2 votes for each ready prince
    or baron" -- `engine/politics.py::TITLE_VOTES["Prince"] == 2`. Proven
    here, end to end through the real `political_action`, to confirm this
    specific printed vampire's `title="Prince"` really is wired to the
    generic title-vote source exactly like any other titled vampire."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Mkhokheli1", capacity=6, blood=1)
    _make_mkhokheli(p1, "Mkhokheli1")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Mkhokheli1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Mkhokheli1"))

    assert result is True  # 1 (political action card) + 2 (Prince title) for vs 0 against
    actor.assert_exhausted()
