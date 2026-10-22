"""Kevin Jackson (krcg id 201629, `src/vtesbot/cards/kevin_jackson.py`).

Card text: "Camarilla Prince of Chicago: Kevin gets +1 strength in combat
with a Brujah. Brujah get +1 strength in combat with him." No rulings on
file.

Three components, one or more assertions each: the registry entry, the
"Camarilla Prince of Chicago" title clause (already generically handled by
`engine/politics.py::TITLE_VOTES`, not this module -- proven end to end
through the real `political_action`, mirroring `tests/cards/
test_valeriya_zinovieva.py`'s own title scenario), and the clan-conditional
combat clause (this module's own effect): both directions of the matchup,
gated on this exact printed card's `krcg_id` for the Kevin side and on
`clan == "Brujah"` for the other side, with negative controls for a
non-Brujah opponent and for a different Ventrue vampire, and an end-to-end
`run_combat` proof that the bonus actually lands as extra damage.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.kevin_jackson import KRCG_ID
from vtesbot.engine import CryptCard, hooks
from vtesbot.engine.combat import COMBAT_STRENGTH_MODIFIER_HOOK, run_combat
from vtesbot.engine.politics import political_action

NAME = "Kevin Jackson"


def _make_kevin(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Kevin Jackson's real printed
    identity (`CryptCard` is frozen, mirrors `tests/cards/
    test_valeriya_zinovieva.py::_make_valeriya`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=7,
        group=7,
        clan="Ventrue",
        title="Prince",
        disciplines=("dom", "for", "pre"),
    )


def test_registered_as_implemented_against_the_combat_strength_modifier_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- "Camarilla Prince of Chicago" -- the title itself, generically handled


def test_a_ready_kevin_contributes_2_votes_as_a_prince_title_source():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Kevin1", capacity=7, blood=1)
    _make_kevin(p1, "Kevin1")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Kevin1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Kevin1"))

    assert result is True  # 1 (political action card) + 2 (Prince title) for vs 0 against
    actor.assert_exhausted()


# --- clan-conditional combat clause -----------------------------------------


def test_kevin_gets_plus_one_strength_against_a_brujah():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Kevin1", capacity=7, blood=0)
    _make_kevin(p1, "Kevin1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0, clan="Brujah")
    game = builder.build()

    bonus = hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK,
        game.state,
        player="P1",
        vampire="Kevin1",
        opponent="B1",
        combat_state=None,
    )

    assert bonus == 1


def test_kevin_gets_no_bonus_against_a_non_brujah():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Kevin1", capacity=7, blood=0)
    _make_kevin(p1, "Kevin1")
    builder.player("P2", pool=30).ready_vampire("T1", capacity=3, blood=0, clan="Toreador")
    game = builder.build()

    bonus = hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK,
        game.state,
        player="P1",
        vampire="Kevin1",
        opponent="T1",
        combat_state=None,
    )

    assert bonus == 0


def test_a_brujah_gets_plus_one_strength_against_kevin():
    """The second, independent sentence: "Brujah get +1 strength in combat
    with him" -- the Brujah side of the matchup, not Kevin's own side."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Kevin1", capacity=7, blood=0)
    _make_kevin(p1, "Kevin1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0, clan="Brujah")
    game = builder.build()

    bonus = hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK,
        game.state,
        player="P2",
        vampire="B1",
        opponent="Kevin1",
        combat_state=None,
    )

    assert bonus == 1


def test_a_different_ventrue_gets_no_bonus_against_a_brujah():
    """Gated on this exact printed card (`krcg_id == KRCG_ID`) for Kevin's
    own side, not on clan/title alone -- a different Ventrue vampire fighting
    a Brujah gets no bonus."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("OtherVentrue", capacity=7, blood=0, clan="Ventrue")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0, clan="Brujah")
    game = builder.build()

    bonus = hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK,
        game.state,
        player="P1",
        vampire="OtherVentrue",
        opponent="B1",
        combat_state=None,
    )

    assert bonus == 0


def test_kevin_hand_strike_deals_2_damage_still_wounds_through_1_mendable_blood():
    """End-to-end through `run_combat`, mirroring `tests/cards/
    test_valeriya_zinovieva.py`'s own mend-math proof: B1 holds exactly 1
    blood, enough to fully mend a plain 1-damage hand strike but not Kevin's
    own 2-damage strike (1 base + this card's +1 against a Brujah)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Kevin1", capacity=7, blood=0)
    _make_kevin(p1, "Kevin1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, clan="Brujah")
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("mend_damage", "1")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("Kevin1"), "P2", game.vampire("B1"))

    assert game.blood_of("B1") == 0
    assert game.vampire("B1").wounded is True
    actor.assert_exhausted()
    defender.assert_exhausted()
