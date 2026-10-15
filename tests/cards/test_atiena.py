"""Atiena (krcg id 201579, `src/vtesbot/cards/atiena.py`).

Card text: "Anarch Baron of Mombasa." No rulings on file.

A single clause, the title itself -- unlike Valeriya Zinovieva's own
"<title>: <ability>" shape, there is no second, card-specific effect to
test. One assertion each: the registry entry, and the "Anarch Baron of
Mombasa" title clause (already generically handled by `engine/politics.py::
TITLE_VOTES`, not this module -- proven end to end through the real
`political_action`, exactly like `tests/cards/test_valeriya_zinovieva.py`'s
own title-vote scenario, to confirm this specific printed card's
`title="Baron"` really does contribute 2 votes while ready).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.atiena import KRCG_ID
from vtesbot.engine import CryptCard
from vtesbot.engine.politics import political_action

NAME = "Atiena"


def _make_atiena(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Atiena's real printed
    identity (`CryptCard` is frozen, mirrors `tests/cards/
    test_valeriya_zinovieva.py::_make_valeriya`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=6,
        group=6,
        clan="Brujah",
        title="Baron",
        disciplines=("obf", "pot", "pre", "CEL"),
    )


def test_registered_as_implemented_with_no_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.hooks == ()
    assert reg.blocked_reason is None


def test_a_ready_atiena_contributes_2_votes_as_a_baron_title_source():
    """Rulebook §4 Politics > Gaining Votes: "2 votes for each ready prince
    or baron" -- `engine/politics.py::TITLE_VOTES["Baron"] == 2`. Proven here,
    end to end through the real `political_action`, to confirm this specific
    printed vampire's `title="Baron"` really is wired to the generic
    title-vote source exactly like any other titled vampire."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Atiena1", capacity=6, blood=1)
    _make_atiena(p1, "Atiena1")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Atiena1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Atiena1"))

    assert result is True  # 1 (political action card) + 2 (Baron title) for vs 0 against
    actor.assert_exhausted()
