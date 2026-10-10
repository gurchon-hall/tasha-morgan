"""Information hiding (CLAUDE.md SS5 engine invariant).

"A bot must not read the opponent's hand, library order or face-down
uncontrolled vampires." This is enforced at the `Observation` boundary: the
engine never hands an agent the raw `GameState`.
"""

from helpers import ScenarioBuilder
from vtesbot.engine import build_observation
from vtesbot.engine.allies import recruit_ally


def test_opponent_hand_contents_are_hidden_but_counted():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1").hand_cards(["Alpha"])
    p2 = builder.player("P2")
    p2.hand_cards(["Secret One", "Secret Two"])
    game = builder.build()

    obs = build_observation(game.state, "P1")

    assert obs.hand == ("Alpha",)
    assert obs.opponent_hand_count == 2


def test_opponent_uncontrolled_vampires_are_anonymous():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1")
    builder.player("P2").uncontrolled_vampire(
        "Secret-V", capacity=4, blood=2, name="Secret Vampire"
    )
    game = builder.build()

    obs = build_observation(game.state, "P1")

    hidden = [v for v in obs.vampires if v.controller == "P2"]
    assert len(hidden) == 1
    assert hidden[0].name is None
    assert hidden[0].capacity is None
    assert hidden[0].blood == 0


def test_own_uncontrolled_vampires_are_fully_visible():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1").uncontrolled_vampire("V1", capacity=4, blood=2, name="My Vampire")
    builder.player("P2")
    game = builder.build()

    obs = build_observation(game.state, "P1")

    own = [v for v in obs.vampires if v.controller == "P1"][0]
    assert own.name == "My Vampire"
    assert own.blood == 2


def test_ready_and_torpor_vampires_are_public_for_both_players():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1")
    builder.player("P2").ready_vampire("V1", capacity=3, blood=1, name=None)
    game = builder.build()

    obs = build_observation(game.state, "P1")

    public = [v for v in obs.vampires if v.controller == "P2"][0]
    assert public.name == "V1"
    assert public.blood == 1


def test_a_recruited_ally_is_fully_visible_to_the_other_player():
    """Rules-auditor finding: an ally in the ready region is public, same as
    a ready vampire (Rulebook SS4 Recruit Ally) -- there is no face-down
    state for an ally to hide (`AllyView`'s own docstring), so the *other*
    player's `Observation` must show its existence and full stats, not just
    a count."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1")
    builder.player("P2")
    game = builder.build()
    ally = recruit_ally(
        game.state, "P2", krcg_id=102217, name="47th Street Royals", life=2, strength=1, bleed=0
    )

    obs = build_observation(game.state, "P1")

    assert len(obs.allies) == 1
    view = obs.allies[0]
    assert view.instance_id == ally.instance_id
    assert view.controller == "P2"
    assert view.name == "47th Street Royals"
    assert view.life == 2
    assert view.strength == 1
    assert view.bleed == 0
    assert view.zone == "ready"
    assert view.locked is True


def test_both_players_allies_appear_in_each_others_observation():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1")
    builder.player("P2")
    game = builder.build()
    recruit_ally(game.state, "P1", krcg_id=1, name="Ally One", life=1)
    recruit_ally(game.state, "P2", krcg_id=2, name="Ally Two", life=1)

    obs_p1 = build_observation(game.state, "P1")
    obs_p2 = build_observation(game.state, "P2")

    assert {a.name for a in obs_p1.allies} == {"Ally One", "Ally Two"}
    assert {a.name for a in obs_p2.allies} == {"Ally One", "Ally Two"}
