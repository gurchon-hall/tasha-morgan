"""Seraphina (krcg id 201686, `src/vtesbot/cards/seraphina.py`).

Card text: "Independent: Seraphina can add 2 blood or life to a minion you
control as a +1 stealth action, not to exceed starting life." No rulings on
file.

One assertion per clause/qualifier: not offered for a different acting
vampire, one option per eligible controlled-vampire/ally target, a vampire
target gets blood capped at effective capacity (ENG-002), an ally target gets
life capped at its own `starting_life` (ENG-041), a target already at its own
cap is never offered, the "+1 stealth action" baseline (undirected, beats a
defender's default 0 intercept), and the blocked branch never adds anything.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.registry import Status, get
from vtesbot.cards.seraphina import KRCG_ID
from vtesbot.engine import CryptCard, hooks
from vtesbot.engine.action import ACTION_ACTION_CARD
from vtesbot.engine.allies import detect_contest_on_recruit, recruit_ally
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, minion_phase

NAME = "Seraphina"


def _make_seraphina(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Seraphina's real printed
    identity (`CryptCard` is frozen)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=8,
        group=7,
        clan="Salubri",
        disciplines=("cel", "tha", "AUS", "DOM", "FOR"),
    )


def test_registered_as_implemented_against_the_action_card_play_hook():
    reg = get(KRCG_ID)
    assert reg is not None
    assert reg.status is Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


def test_not_offered_for_a_different_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert options == []


def test_offers_one_option_per_eligible_vampire_and_ally():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=8, blood=0)
    p1.ready_vampire("W1", capacity=3, blood=0)
    _make_seraphina(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)
    ally.life = 2  # below its own starting_life, so there is room to add life.

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    values = {o.choice.value for o in options}
    assert values == {
        "seraphina:blood:V1",
        "seraphina:blood:W1",
        "seraphina:life:P1-A1",
    }


def test_blood_target_is_capped_at_effective_capacity():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=8, blood=0)
    p1.ready_vampire("W1", capacity=3, blood=2)
    _make_seraphina(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()

    (option,) = [
        o
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
        if o.choice.value == "seraphina:blood:W1"
    ]
    spec = option.apply(game.state)
    spec.resolve({})

    assert game.blood_of("W1") == 3  # capped at capacity 3, not +2 to 4


def test_life_target_is_capped_at_its_own_starting_life():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=8, blood=0)
    _make_seraphina(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)
    ally.life = 3

    (option,) = [
        o
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
        if o.choice.value.startswith("seraphina:life:")
    ]
    spec = option.apply(game.state)
    spec.resolve({})

    assert ally.life == 4  # capped at starting_life 4, not +2 to 5


def test_a_vampire_already_at_capacity_is_not_offered():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=8, blood=0)
    p1.ready_vampire("W1", capacity=3, blood=3)
    _make_seraphina(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert "seraphina:blood:W1" not in {o.choice.value for o in options}


def test_an_ally_already_at_starting_life_is_not_offered():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=8, blood=0)
    _make_seraphina(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()
    recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert not any(o.choice.value.startswith("seraphina:life:") for o in options)


def test_a_contested_ally_is_not_offered():
    """ENG-004: the 2P variant's "stays in play, usable" override is scoped to
    crypt cards only -- a contested *ally* is not "in play, usable", unlike
    a contested vampire, so it must not be targetable."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=8, blood=0)
    _make_seraphina(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()
    mine = recruit_ally(game.state, "P1", krcg_id=999999, name="Shared Ally", life=4)
    mine.zone = "ready"
    theirs = recruit_ally(game.state, "P2", krcg_id=999999, name="Shared Ally", life=4)
    detect_contest_on_recruit(game.state, theirs)
    assert mine.zone == "contested"  # sanity: the contest was actually detected.

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert not any(o.choice.value.startswith("seraphina:life:") for o in options)


def test_base_stealth_is_one_and_directed_is_false():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=8, blood=0)
    p1.ready_vampire("W1", capacity=3, blood=0)
    _make_seraphina(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()

    (option,) = [
        o
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
        if o.choice.value == "seraphina:blood:W1"
    ]
    spec = option.apply(game.state)

    assert spec.base_stealth == 1
    assert spec.directed is False


def test_unblocked_adds_blood_via_minion_phase():
    """A single ready vampire (Seraphina herself, targeting herself) keeps
    the scenario free of the Rulebook's unrelated mandatory "a ready,
    unlocked vampire with no blood must hunt" rule (`engine/phases/
    minion.py::minion_phase`) -- `blood=1` on Seraphina herself sidesteps it
    too."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=8, blood=1)
    _make_seraphina(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "seraphina:blood:V1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.blood_of("V1") == 3
    actor.assert_exhausted()


def test_blocked_does_not_resolve_nothing_is_added():
    """Base stealth 1 needs a matching +1 intercept to actually succeed a
    block attempt; a temporary fake `"intercept_modifier"` provider (gated
    on this card's own default `ACTION_ACTION_CARD` discriminator) stands in
    for some other intercept-granting card so this test can reach the
    blocked branch (mirrors `tests/cards/test_sakhar.py`'s own identically
    shaped precedent)."""

    def match_stealth(state, context):
        if context.get("action") != ACTION_ACTION_CARD:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_stealth)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=8, blood=1)
        _make_seraphina(p1, "V1")
        builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1)
        game = builder.build()

        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "seraphina:blood:V1")
        actor.expect("strike_choice", "no_strike")
        actor.expect("press", "end_combat")
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B1")
        defender.expect("intercept_modifier", "match")
        defender.expect("strike_choice", "no_strike")
        defender.expect("press", "end_combat")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        minion_phase(game.state, "P1")

        assert game.blood_of("V1") == 1  # unchanged: blocked, never resolved.
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_stealth)
