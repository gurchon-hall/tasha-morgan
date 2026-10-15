"""Valeriya Zinovieva (krcg id 201614, `src/vtesbot/cards/valeriya_zinovieva.py`).

Card text: "Anarch Baron of Moscow: +1 strength." No rulings on file.

Two components, one assertion each: the "Anarch Baron of Moscow" title
clause (already generically handled by `engine/politics.py::TITLE_VOTES`,
not this module -- proven end to end through the real `political_action`,
exactly like `tests/cards/test_marcos_belegrad.py`'s own title-vote
scenarios, to confirm this specific printed card's `title="Baron"` really
does contribute 2 votes while ready), and the "+1 strength" clause (this
module's own effect): granted only to this exact printed vampire's own
strikes, never to a different vampire and never to the opponent's side of
the same strike, proven both directly against `COMBAT_STRENGTH_MODIFIER_
HOOK`/`hooks.sum_modifiers` and end-to-end through `run_combat`'s own
mend-math (a strike that lands for 2 damage against a single point of
mendable blood still leaves the target wounded, unlike a plain 1-damage
hand strike against the same blood total).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.valeriya_zinovieva import KRCG_ID
from vtesbot.engine import CryptCard, hooks
from vtesbot.engine.combat import COMBAT_STRENGTH_MODIFIER_HOOK, run_combat
from vtesbot.engine.politics import political_action

NAME = "Valeriya Zinovieva"


def _make_valeriya(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Valeriya Zinovieva's real
    printed identity (`CryptCard` is frozen, mirrors `tests/cards/
    test_marcos_belegrad.py::_make_marcos`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=7,
        group=6,
        clan="Brujah",
        title="Baron",
        disciplines=("cel", "pre", "pro", "POT"),
    )


def test_registered_as_implemented_against_the_combat_strength_modifier_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- "Anarch Baron of Moscow" -- the title itself, generically handled -----


def test_a_ready_valeriya_contributes_2_votes_as_a_baron_title_source():
    """Rulebook §4 Politics > Gaining Votes: "2 votes for each ready prince
    or baron" -- `engine/politics.py::TITLE_VOTES["Baron"] == 2`. This is not
    this card module's own code (no card-specific hook is needed for it),
    but is proven here, end to end through the real `political_action`, to
    confirm this specific printed vampire's `title="Baron"` really is wired
    to the generic title-vote source exactly like any other titled vampire."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Valeriya1", capacity=7, blood=1)
    _make_valeriya(p1, "Valeriya1")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Valeriya1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Valeriya1"))

    assert result is True  # 1 (political action card) + 2 (Baron title) for vs 0 against
    actor.assert_exhausted()


# --- "+1 strength" -- this module's own effect ------------------------------


def test_valeriya_grants_plus_one_strength_to_her_own_strike():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Valeriya1", capacity=7, blood=0)
    _make_valeriya(p1, "Valeriya1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    bonus = hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK, game.state, player="P1", vampire="Valeriya1", opponent="B1"
    )

    assert bonus == 1


def test_valeriya_grants_no_bonus_to_a_different_vampire():
    """Gated on this exact printed card (`krcg_id == KRCG_ID`), not on clan,
    title or any other generic attribute -- a different, non-Valeriya
    vampire gets no bonus even while controlled by the same player."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Valeriya1", capacity=7, blood=0)
    _make_valeriya(p1, "Valeriya1")
    p1.ready_vampire("Other", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    bonus = hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK, game.state, player="P1", vampire="Other", opponent="B1"
    )

    assert bonus == 0


def test_valeriya_grants_no_bonus_to_the_opponents_side_of_the_same_strike():
    """The bonus is Valeriya's own strength, never a bonus the opponent's
    combatant picks up by merely being in the same matchup."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Valeriya1", capacity=7, blood=0)
    _make_valeriya(p1, "Valeriya1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    bonus = hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK, game.state, player="P2", vampire="B1", opponent="Valeriya1"
    )

    assert bonus == 0


def test_valeriya_hand_strike_deals_2_damage_still_wounds_through_1_mendable_blood():
    """End-to-end through `run_combat`: B1 holds exactly 1 blood, enough to
    fully mend a plain 1-damage hand strike (see `tests/rules/
    test_combat.py::test_combat_round_with_mend_and_declined_press`'s own
    2-blood/1-damage baseline) but not Valeriya's own 2-damage strike (1
    base + this card's +1): B1 mends the 1 point it can, and is left wounded
    by the remaining, unmended point -- observable proof the strike actually
    landed for 2, not 1."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Valeriya1", capacity=7, blood=0)
    _make_valeriya(p1, "Valeriya1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
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

    run_combat(game.state, "P1", game.vampire("Valeriya1"), "P2", game.vampire("B1"))

    assert game.blood_of("B1") == 0  # mended 1 of the 2 damage taken
    assert game.vampire("B1").wounded is True  # the remaining point still landed
    assert game.zone_of("B1") == "ready"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_plain_hand_strike_against_the_same_1_blood_does_not_wound():
    """Baseline/control for the test above: without Valeriya's bonus, the
    same 1 point of blood fully mends a plain 1-damage hand strike, and B1
    is never wounded at all."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
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

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.blood_of("B1") == 0
    assert game.vampire("B1").wounded is False
    actor.assert_exhausted()
    defender.assert_exhausted()
