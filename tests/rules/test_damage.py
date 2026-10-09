"""Damage resolution: prevent, then mend; unmended -> wounded -> torpor;
aggravated cannot be mended (Rulebook SS4 Combat > Damage Resolution).

Reproduces the `rules-scenario-test` skill's own worked example for
aggravated damage: "a ready vampire with 1 blood takes 2 normal + 1
aggravated damage; burns 1 blood to mend, is wounded by the 2nd point, and
the aggravated point burns him."
"""

from helpers import ScenarioBuilder, ScriptedAgent


def _one_vampire_game(capacity: int = 3, blood: int = 0, wounded: bool = False):
    builder = ScenarioBuilder(seed=1)
    builder.player("A").ready_vampire("V1", capacity=capacity, blood=blood, wounded=wounded)
    builder.player("B")
    return builder.build()


def test_aggravated_damage_burns_an_already_wounded_vampire():
    game = _one_vampire_game(capacity=3, blood=1)
    game.state.agents["A"] = ScriptedAgent("A").expect("mend_damage", "1")

    game.apply_damage(target="V1", normal=2, aggravated=1, source=None)

    assert game.zone_of("V1") == "burned"


def test_first_unmended_normal_damage_wounds_not_torpors():
    game = _one_vampire_game(capacity=3, blood=0)
    game.state.agents["A"] = ScriptedAgent("A")  # blood=0: no mend decision offered

    game.apply_damage(target="V1", normal=1)

    assert game.vampire("V1").wounded is True
    assert game.zone_of("V1") == "ready"


def test_second_unmended_normal_damage_on_wounded_vampire_sends_to_torpor():
    game = _one_vampire_game(capacity=3, blood=0, wounded=True)
    game.state.agents["A"] = ScriptedAgent("A")

    game.apply_damage(target="V1", normal=1)

    assert game.zone_of("V1") == "torpor"


def test_aggravated_damage_on_a_healthy_vampire_wounds_and_torpors_at_once():
    """Rulebook worked example (Nassir): a ready vampire with 1 blood takes 1
    aggravated damage. He cannot mend it, so he is wounded *and* goes to
    torpor with 1 blood -- unlike normal damage, a healthy vampire has no
    "merely wounded, still ready" state for aggravated damage."""
    game = _one_vampire_game(capacity=3, blood=1)
    game.state.agents["A"] = ScriptedAgent("A")  # aggravated is never mendable: no decision offered

    game.apply_damage(target="V1", aggravated=1)

    assert game.zone_of("V1") == "torpor"
    assert game.blood_of("V1") == 1
    assert game.vampire("V1").wounded is True


def test_multiple_aggravated_points_wound_torpor_then_burn_blood():
    """Rulebook worked example (Tamoszius): a ready vampire with 2 blood takes
    3 aggravated damage. The first point wounds and torpors him; the
    remaining two points (now against an already-wounded vampire) each burn
    1 blood; he ends in torpor with no blood."""
    game = _one_vampire_game(capacity=3, blood=2)
    game.state.agents["A"] = ScriptedAgent("A")

    game.apply_damage(target="V1", aggravated=3)

    assert game.zone_of("V1") == "torpor"
    assert game.blood_of("V1") == 0


def test_fully_mended_damage_leaves_vampire_undamaged():
    game = _one_vampire_game(capacity=3, blood=3)
    game.state.agents["A"] = ScriptedAgent("A").expect("mend_damage", "2")

    game.apply_damage(target="V1", normal=2)

    assert game.vampire("V1").wounded is False
    assert game.blood_of("V1") == 1


def test_mend_decision_offers_full_range_including_declining_to_mend():
    """Decision points are explicit: 0 (decline) through the maximum
    affordable mend are all legal choices; the engine never mends for the
    player."""
    offered: list[str] = []

    class RecordingAgent:
        def decide(self, observation, decision):
            offered.extend(c.value for c in decision.choices)
            return decision.choices[0]

    game = _one_vampire_game(capacity=5, blood=3)
    game.state.agents["A"] = RecordingAgent()

    game.apply_damage(target="V1", normal=2)

    assert offered == ["0", "1", "2"]


def test_no_mend_decision_when_vampire_has_no_blood():
    """ "Only when needed": a vampire with 0 blood has nothing to mend with,
    so no `mend_damage` decision is raised."""
    game = _one_vampire_game(capacity=3, blood=0)
    game.state.agents["A"] = ScriptedAgent("A")  # would fail loudly if a decision were raised

    game.apply_damage(target="V1", normal=1)

    assert game.vampire("V1").wounded is True
