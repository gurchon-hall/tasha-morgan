"""Vote sources gained while votes are cast (ENG-051): Rulebook §4 The
Referendum, Polling. A "during the polling step" card stays usable until the
polling stage ends; its source is castable from the player's next step."""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.politics import POLLING_STEP_HOOK, resolve_referendum


def _game():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    return builder.build()


def _mid_cast_source(player: str, votes: int, *, abstain_first: bool = False):
    """Test-only provider: once per referendum, `player` gains a source."""
    source_id = f"fake:{player}"

    def provider(state, context):
        pending = context["pending"]
        if context["player"] != player or pending.get(source_id):
            return []
        if context["phase"] == "before_cast":
            if not abstain_first:
                return []

            def _abstain(s):
                pending["forced_abstain"].add(source_id)

            return [HookOption(choice=Choice("fake_abstain", "Abstain"), apply=_abstain)]

        def _add(s):
            pending[source_id] = True
            pending["extra_sources"].append(
                {"source_id": source_id, "player": player, "votes": votes, "label": "Fake"}
            )

        return [HookOption(choice=Choice("fake_add", "Gain votes"), apply=_add)]

    hooks.register(POLLING_STEP_HOOK, provider)


def test_non_caller_source_gained_after_the_caller_passed_is_castable():
    _mid_cast_source("P2", votes=2)
    game = _game()
    caller = ScriptedAgent("P1")
    caller.expect("polling_step_cast", "pass")
    caller.expect("polling_step_cast", "for:political_action_card:P1")
    other = ScriptedAgent("P2")
    other.expect("polling_step_cast", "fake_add")
    other.expect("polling_step_cast", "against:fake:P2")
    game.state.agents["P1"] = caller
    game.state.agents["P2"] = other

    votes_for, votes_against, _ = resolve_referendum(game.state, "P1", "P2", game.vampire("V1"))

    assert (votes_for, votes_against) == (1, 2)
    caller.assert_exhausted()
    other.assert_exhausted()


def test_a_source_forced_to_abstain_is_not_castable_when_gained_mid_cast():
    _mid_cast_source("P1", votes=2, abstain_first=True)
    game = _game()
    caller = ScriptedAgent("P1")
    caller.expect(POLLING_STEP_HOOK, "fake_abstain")
    caller.expect(POLLING_STEP_HOOK, "pass")
    caller.expect("polling_step_cast", "fake_add")
    caller.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = caller
    game.state.agents["P2"] = ScriptedAgent("P2")

    votes_for, votes_against, casts = resolve_referendum(game.state, "P1", "P2", game.vampire("V1"))

    assert (votes_for, votes_against) == (1, 0)
    assert [cast[1] for cast in casts] == ["political_action_card:P1"]
    caller.assert_exhausted()
