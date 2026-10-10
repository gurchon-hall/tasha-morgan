"""Marcos Belegrad (krcg id 201702, `src/vtesbot/cards/marcos_belegrad.py`).

Card text: "Camarilla Prince of Bogota: Methuselahs casting (including
controlling a minion casting) votes or ballots against a referendum called
by Marcos burn 1 pool once results are tallied." No rulings on file.

One assertion per clause/behaviour: the mandatory "once results are
tallied" timing (fires regardless of the referendum's own pass/fail
outcome), the flat "1 pool" amount (not scaled by vote count or by how many
separate sources one Methuselah cast against), "including controlling a
minion casting" (a titled vampire's own vote source, whose `player` is its
controller), the calling Methuselah not being exempt from their own card's
effect, and the "called *by Marcos*" scoping (this specific vampire
instance, not just its controller, who may also control some other titled
vampire) -- built on top of the real, production `engine/politics.py::
political_action`/`resolve_referendum`, exactly like `tests/rules/
test_politics.py`'s own scenarios, with the acting/other vampire's `card`
swapped for Marcos's real printed identity where the test calls for it.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.marcos_belegrad import KRCG_ID
from vtesbot.engine import CryptCard
from vtesbot.engine.politics import political_action


def _make_marcos(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Marcos Belegrad's real
    printed identity (`CryptCard` is frozen, mirrors `tests/cards/
    test_forty_seventh_street_royals.py::_set_clan`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name="Marcos Belegrad",
        capacity=8,
        group=7,
        clan="Toreador",
        title="Prince",
        disciplines=("ani", "AUS", "CEL", "PRE"),
    )


def test_registered_as_implemented_against_the_referendum_tallied_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Marcos Belegrad"
    assert reg.blocked_reason is None


def test_nobody_loses_pool_when_nobody_casts_against_marcos_referendum():
    """Baseline: with no "against" cast at all, Marcos's reaction never
    fires for anyone."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Marcos1", capacity=8, blood=1)
    _make_marcos(p1, "Marcos1")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "pass")  # decline Marcos's own title vote
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Marcos1"))

    assert result is True  # 1 for (political action card), 0 against
    assert game.pool_of("P1") == 30
    assert game.pool_of("P2") == 30
    actor.assert_exhausted()


def test_other_methuselah_casting_against_burns_1_pool_even_though_referendum_still_passes():
    """ "Methuselahs casting ... against a referendum called by Marcos burn 1
    pool once results are tallied" fires for the other Methuselah even
    though Marcos's side still wins the tally overall (3 for vs 1 against)
    -- the effect is not conditioned on the referendum failing. The "against"
    source here is a titled vampire's own vote ("including controlling a
    minion casting"): `source.player` for a title-vote source is already its
    controller, exactly what that clause means."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Marcos1", capacity=8, blood=1)
    _make_marcos(p1, "Marcos1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Marcos1")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("Marcos1"))

    # 1 (political action card) + 2 (Marcos's own Prince title) for vs 1 (B1
    # Primogen) against: 3-1, passes.
    assert result is True
    assert game.pool_of("P1") == 30  # P1 never cast against: no loss
    assert game.pool_of("P2") == 29  # P2 cast against: burns 1 pool
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_the_calling_methuselah_is_not_exempt_from_their_own_marcos_referendum():
    """No special case for the caller: Marcos's controller casting their own
    vote against their own referendum burns 1 pool too, same as any other
    Methuselah casting against."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Marcos1", capacity=8, blood=1)
    _make_marcos(p1, "Marcos1")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "against:political_action_card:P1")
    actor.expect("polling_step_cast", "pass")  # decline Marcos's own title vote
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Marcos1"))

    assert result is False  # 0 for, 1 against: fails
    assert game.pool_of("P1") == 29  # P1 cast against their own referendum
    actor.assert_exhausted()


def test_one_methuselah_casting_two_sources_against_still_burns_only_1_pool_total():
    """The printed text says a flat "burn 1 pool", not "1 pool per vote" or
    "1 pool per source cast against" -- a Methuselah who casts two separate
    sources against the same referendum (here, a titled vampire's vote and
    the Edge) still only burns 1 pool total, not 2."""
    builder = ScenarioBuilder(seed=1).edge_holder("P2")
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Marcos1", capacity=8, blood=1)
    _make_marcos(p1, "Marcos1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "pass")
    actor.expect("polling_step_cast", "pass")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "against:title:B1")
    defender.expect("polling_step_cast", "against:edge:P2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("Marcos1"))

    # 1 for (political action card; Marcos's own title vote declined) vs 2
    # against (B1's Primogen title + the burned Edge): fails.
    assert result is False
    assert game.pool_of("P1") == 30
    assert game.pool_of("P2") == 29  # only 1 pool lost, not 2, for the two against-casts
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_referendum_called_by_a_different_titled_vampire_never_triggers_marcos():
    """ "called by Marcos" scopes the effect to referenda announced by this
    specific Marcos instance, not to any referendum this card's controller
    happens to call -- here P1 controls both Marcos (idle) and a different
    titled vampire ("Other"), who is the one that actually calls the
    referendum; P2 casts against it, but Marcos's reaction must never fire,
    since `context["caller_vampire"]` is "Other", not Marcos."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Other", capacity=4, blood=1, title="Primogen")
    p1.ready_vampire("Marcos1", capacity=8, blood=1)
    _make_marcos(p1, "Marcos1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "pass")  # decline both Other's and Marcos's title votes
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("Other"))

    assert result is False  # 1 for vs 1 against: ties and fails
    assert game.pool_of("P1") == 30
    assert game.pool_of("P2") == 30  # Marcos never triggers: this was not his referendum
    actor.assert_exhausted()
    defender.assert_exhausted()
