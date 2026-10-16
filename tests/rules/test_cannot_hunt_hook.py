"""`engine/phases/minion.py::CANNOT_HUNT_HOOK`: an attachment-driven
override of `minion_phase`'s own mandatory-hunt loop ("a ready unlocked
vampire with no blood must hunt", Rulebook §4). A passive boolean hook
(`hooks.any_true`, mirrors `attachments.py::CAPACITY_MODIFIER_HOOK`'s own
"mandatory and always-on" shape, CLAUDE.md rule 3 exception): when any
provider returns True for a vampire that must hunt, it is sent straight to
torpor instead (`engine/damage.py::send_to_torpor`) -- not an action, never
blockable.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake attachment (sentinel `krcg_id`, mirrors
`tests/rules/test_attachments.py`'s own convention) standing in for Pulled
Fangs' (krcg 101515) own "The attached vampire cannot hunt; if they must
hunt, they go to torpor instead." -- that card's own wiring remains
`card-implementer`'s job once this capability exists; it stays registered
`blocked` until then.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.phases.minion import CANNOT_HUNT_HOOK, minion_phase

FAKE_ATTACHMENT_KRCG_ID = 999999


def _fake_cannot_hunt_provider(state, context):
    """Stand-in for Pulled Fangs' own provider: only True while the fake
    attachment is actually on this exact vampire (CLAUDE.md §6: the card
    module recognizes its own attachment, the engine never special-cases a
    card name)."""
    vampire_id = context["vampire"]
    for player_state in state.players.values():
        vampire = player_state.vampires.get(vampire_id)
        if vampire is not None:
            return any(a.krcg_id == FAKE_ATTACHMENT_KRCG_ID for a in vampire.attachments)
    return False


def test_attached_vampire_with_no_blood_goes_to_torpor_instead_of_hunting():
    hooks.register(CANNOT_HUNT_HOOK, _fake_cannot_hunt_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=FAKE_ATTACHMENT_KRCG_ID, name="X"
    )
    # No "hunt"/block decision at all: forced straight to torpor, not an action.
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.zone_of("V1") == "torpor"
    assert game.vampire("V1").locked is False
    assert game.blood_of("V1") == 0  # never actually hunted


def test_zero_regression_unattached_vampire_still_hunts_normally():
    hooks.register(CANNOT_HUNT_HOOK, _fake_cannot_hunt_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    # No attachment at all: the provider returns False, hunt proceeds as normal.
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.zone_of("V1") == "ready"
    assert game.blood_of("V1") == 1
    assert game.vampire("V1").locked is True


def test_attached_vampire_with_blood_is_unaffected_not_subject_to_mandatory_hunt():
    """`CANNOT_HUNT_HOOK` only matters while the mandatory-hunt loop would
    otherwise fire -- a vampire that already has blood is never even
    checked against it."""
    hooks.register(CANNOT_HUNT_HOOK, _fake_cannot_hunt_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=FAKE_ATTACHMENT_KRCG_ID, name="X"
    )
    actor = ScriptedAgent("P1").expect("minion_phase_choice", "end_minion_phase")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.zone_of("V1") == "ready"
    assert game.vampire("V1").locked is False
    actor.assert_exhausted()


def test_with_two_vampires_only_the_attached_one_is_redirected_to_torpor():
    hooks.register(CANNOT_HUNT_HOOK, _fake_cannot_hunt_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0).ready_vampire(
        "V2", capacity=3, blood=0
    )
    builder.player("P2", pool=30)
    game = builder.build()
    attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=FAKE_ATTACHMENT_KRCG_ID, name="X"
    )
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.zone_of("V1") == "torpor"
    assert game.zone_of("V2") == "ready"
    assert game.blood_of("V2") == 1  # V2 hunted normally
