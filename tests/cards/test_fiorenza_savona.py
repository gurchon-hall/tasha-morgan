"""Fiorenza Savona (krcg id 201616, `src/vtesbot/cards/fiorenza_savona.py`).

Card text: "Camarilla: If you burn the Edge for a vote, you get +1 vote. If
you burn a political action card for a vote, you get +1 vote." No rulings
on file.

ENG-031 (resolved): both clauses are proven directly
against the new `VOTE_SOURCE_CAST_BONUS_HOOK` (gating: which flag is set,
whether the caster actually controls an in-play Fiorenza) and once end to
end through a real `political_action`, where the bonus is the deciding
margin between a tied (failing) referendum and a passing one.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.fiorenza_savona import KRCG_ID
from vtesbot.engine import CryptCard, hooks
from vtesbot.engine.politics import VOTE_SOURCE_CAST_BONUS_HOOK, political_action

NAME = "Fiorenza Savona"


def _make_fiorenza(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Fiorenza Savona's real
    printed identity (`CryptCard` is frozen)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=7,
        group=6,
        clan="Ventrue",
        disciplines=(),
    )


def test_registered_as_implemented_against_the_vote_source_cast_bonus_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- the hook directly -------------------------------------------------


def test_no_bonus_when_neither_edge_nor_pac_burn_flag_is_set():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Fiorenza1", capacity=7, blood=1)
    _make_fiorenza(p1, "Fiorenza1")
    builder.player("P2", pool=30)
    game = builder.build()

    bonus = hooks.sum_modifiers(
        VOTE_SOURCE_CAST_BONUS_HOOK,
        game.state,
        caster="P1",
        burns_edge=False,
        burns_pac_from_hand=False,
    )

    assert bonus == 0


def test_plus_one_when_fiorenzas_controller_burns_the_edge():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Fiorenza1", capacity=7, blood=1)
    _make_fiorenza(p1, "Fiorenza1")
    builder.player("P2", pool=30)
    game = builder.build()

    bonus = hooks.sum_modifiers(
        VOTE_SOURCE_CAST_BONUS_HOOK,
        game.state,
        caster="P1",
        burns_edge=True,
        burns_pac_from_hand=False,
    )

    assert bonus == 1


def test_plus_one_when_fiorenzas_controller_burns_a_political_action_card():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Fiorenza1", capacity=7, blood=1)
    _make_fiorenza(p1, "Fiorenza1")
    builder.player("P2", pool=30)
    game = builder.build()

    bonus = hooks.sum_modifiers(
        VOTE_SOURCE_CAST_BONUS_HOOK,
        game.state,
        caster="P1",
        burns_edge=False,
        burns_pac_from_hand=True,
    )

    assert bonus == 1


def test_no_bonus_for_a_methuselah_who_does_not_control_fiorenza():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()

    bonus = hooks.sum_modifiers(
        VOTE_SOURCE_CAST_BONUS_HOOK,
        game.state,
        caster="P1",
        burns_edge=True,
        burns_pac_from_hand=False,
    )

    assert bonus == 0


def test_no_zone_qualifier_torpid_fiorenza_still_grants_the_bonus():
    """No "while ready" clause is printed (contrast Carmelita Neillson), so
    a torpid Fiorenza -- still controlled, still in play -- still grants
    it."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.torpid_vampire("Fiorenza1", capacity=7, blood=0)
    _make_fiorenza(p1, "Fiorenza1")
    builder.player("P2", pool=30)
    game = builder.build()

    bonus = hooks.sum_modifiers(
        VOTE_SOURCE_CAST_BONUS_HOOK,
        game.state,
        caster="P1",
        burns_edge=True,
        burns_pac_from_hand=False,
    )

    assert bonus == 1


def test_an_uncontrolled_not_yet_revealed_fiorenza_grants_no_bonus():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.uncontrolled_vampire("Fiorenza1", capacity=7, blood=0)
    _make_fiorenza(p1, "Fiorenza1")
    builder.player("P2", pool=30)
    game = builder.build()

    bonus = hooks.sum_modifiers(
        VOTE_SOURCE_CAST_BONUS_HOOK,
        game.state,
        caster="P1",
        burns_edge=True,
        burns_pac_from_hand=False,
    )

    assert bonus == 0


# --- end to end through a real political_action ------------------------


def test_the_bonus_is_the_margin_between_a_tied_and_a_passing_referendum():
    """P1 (the caller) casts their own political-action-card vote *against*
    their own referendum; P2, who controls Fiorenza and holds the Edge,
    burns it *for*. Without Fiorenza's bonus this would be a 1-1 tie (Tied
    referendums fail); with it, P2's Edge cast is worth 2, so it passes."""
    builder = ScenarioBuilder(seed=1).edge_holder("P2")
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("Fiorenza1", capacity=7, blood=1)
    _make_fiorenza(p2, "Fiorenza1")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "against:political_action_card:P1")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "for:edge:P2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is True  # 2 (edge: 1 base + 1 Fiorenza) for vs 1 against
    assert game.state.edge_holder is None
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_mid_cast_cancellation_of_the_bonused_source_subtracts_the_full_total():
    """ENG-027/ENG-031 interaction: cancelling a source that already carried
    Fiorenza's bonus must retroactively remove the *whole* cast amount
    (base + bonus), not just the base `VoteSource.votes` -- otherwise the
    bonus would silently survive a cancellation of its own source."""
    from vtesbot.engine.decision import Choice
    from vtesbot.engine.hooks import HookOption
    from vtesbot.engine.politics import POLLING_STEP_HOOK

    def fake_cancel(state, context):
        if context.get("phase") != "mid_cast" or context.get("player") != "P1":
            return []
        targets = [c[1] for c in context["casts"] if c[1] == "edge:P2"]
        if not targets:
            return []

        def apply(s):
            return "edge:P2"

        return [HookOption(choice=Choice("cancel_edge", "Cancel P2's Edge vote"), apply=apply)]

    hooks.register(POLLING_STEP_HOOK, fake_cancel)
    builder = ScenarioBuilder(seed=1).edge_holder("P2")
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("Fiorenza1", capacity=7, blood=1)
    _make_fiorenza(p2, "Fiorenza1")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "pass")
    actor.expect("polling_step_cast", "cancel_edge")
    actor.expect("polling_step_cast", "pass")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "for:edge:P2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is False  # the bonused "for" cast was fully cancelled: 0 for vs 0 against
    actor.assert_exhausted()
    defender.assert_exhausted()
