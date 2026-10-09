"""Information hiding (CLAUDE.md SS5 engine invariant).

"A bot must not read the opponent's hand, library order or face-down
uncontrolled vampires." This is enforced at the `Observation` boundary: the
engine never hands an agent the raw `GameState`.
"""

from helpers import ScenarioBuilder
from vtesbot.engine import build_observation


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
