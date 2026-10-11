"""Modius (krcg id 201703, `src/vtesbot/cards/modius.py`).

Card text: "Camarilla Prince of Gary: During the polling step of any
referendum, Modius can discard a master card to get +1 vote."

Rulings:
    - "The ability can be used when in torpor. [LSJ 20011022]" -- a
      dedicated test below proves Modius still grants the vote while
      `zone == "torpor"`.
    - "Cannot be used during a referendum that is automatically passing.
      [PIB 20150105] [LSJ 19980107]" -- `src/vtesbot/cards/modius.py`'s own
      module docstring explains why this is not testable in this engine
      today: no card implemented (or implementable yet) produces an
      "automatically passing" referendum, so `engine/politics.py::
      resolve_referendum` never has such a code path to interact with.

One assertion per clause/behaviour: "during the polling step of any
referendum" (usable even when Modius's own controller did not call it),
"can discard" (optional, never forced), "a master card" (gated on
`card_type == "Master"` specifically, not any hand card), "+1 vote" (a new
castable vote source, on top of whatever Modius's own ready Prince title
vote would separately contribute), the torpor ruling, and "discard" being a
plain hand-to-ash-heap move with no replacement draw.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.modius import KRCG_ID
from vtesbot.engine import CryptCard
from vtesbot.engine.politics import POLLING_STEP_HOOK, political_action


def _make_modius(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Modius's real printed
    identity (`CryptCard` is frozen, mirrors `tests/cards/
    test_forty_seventh_street_royals.py::_set_clan`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name="Modius",
        capacity=8,
        group=7,
        clan="Toreador",
        title="Prince",
        disciplines=("obf", "AUS", "CEL", "PRE"),
    )


def test_registered_as_implemented_against_the_polling_step_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Modius"
    assert reg.blocked_reason is None


def test_modius_discards_a_master_card_for_1_vote_while_ready():
    """Modius himself calls the referendum here (ready, unlocked at
    announce-time per `political_action`'s own locking, but that has no
    bearing on voting): his controller discards the one master card in hand
    during the pre-cast polling step window for a brand-new +1 vote source,
    cast "for" alongside the political-action-card vote and Modius's own
    (separately-modeled, generic) ready Prince title vote."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Modius1", capacity=8, blood=1)
    _make_modius(p1, "Modius1")
    p1.hand_cards(["Fake Master"], card_type="Master")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, "modius_discard_master:Modius1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Modius1")
    actor.expect("polling_step_cast", "for:modius:Modius1:0")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Modius1"))

    # 1 (political action card) + 2 (Modius's own ready Prince title) + 1
    # (Modius's discard-a-master-card ability) for vs 0 against: passes.
    assert result is True
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Fake Master"]
    assert game.pool_of("P1") == 30  # the cost is a discarded card, never pool
    actor.assert_exhausted()


def test_modius_ability_is_usable_while_modius_is_in_torpor():
    """[LSJ 20011022]: "The ability can be used when in torpor." Modius sits
    in torpor the whole time (a separate vampire calls the referendum); his
    generic ready-titled-vampire vote (worth 2, Prince) correctly does
    *not* apply while torpid (Rulebook SS4 Politics > Gaining Votes, "a
    vampire's `zone == 'ready'`" gate -- unaffected by this card), but his
    own printed discard-for-+1-vote ability still fires. The vote math below
    only passes (2 for vs 1 against) if the torpor ability actually fired;
    if it had been wrongly blocked, the tally would tie at 1-1 and fail,
    distinguishing the two outcomes."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Caller", capacity=4, blood=1)
    p1.torpid_vampire("Modius1", capacity=8, blood=0)
    _make_modius(p1, "Modius1")
    p1.hand_cards(["Fake Master"], card_type="Master")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, "modius_discard_master:Modius1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:modius:Modius1:0")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("Caller"))

    assert result is True  # 2 for (political action card + Modius's ability) vs 1 against
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Fake Master"]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_modius_not_offered_without_a_master_card_in_hand():
    """ "a master card" -- gated on `card_type == "Master"` specifically;
    holding only a non-master card never offers the ability (proven by
    omission: no `POLLING_STEP_HOOK` decision is scripted, and
    `ScriptedAgent` fails loudly on any unscripted decision)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Modius1", capacity=8, blood=1)
    _make_modius(p1, "Modius1")
    p1.hand_cards(["Fake Reaction"], card_type="Reaction")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "pass")  # decline Modius's own title vote
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Modius1"))

    assert result is True
    assert [c.name for c in game.state.players["P1"].hand] == ["Fake Reaction"]
    assert game.state.players["P1"].ash_heap == []
    actor.assert_exhausted()


def test_modius_not_offered_while_uncontrolled():
    """Modius's ability requires him actually in play (ready or torpor);
    an `"uncontrolled"` crypt card (not yet claimed by either Methuselah) is
    neither, so the ability is never offered even while holding a master
    card -- a separate, ready vampire calls the referendum instead."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Caller", capacity=4, blood=1)
    p1.uncontrolled_vampire("Modius1", capacity=8)
    _make_modius(p1, "Modius1")
    p1.hand_cards(["Fake Master"], card_type="Master")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Caller"))

    assert result is True
    assert [c.name for c in game.state.players["P1"].hand] == ["Fake Master"]
    assert game.state.players["P1"].ash_heap == []
    actor.assert_exhausted()


def test_modius_usable_on_a_referendum_called_by_the_other_methuselah():
    """ "During the polling step of any referendum" -- not only ones
    Modius's own controller calls. P1 calls the referendum; P2 (not the
    caller) controls Modius and still gets the ability offered."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("Caller", capacity=4, blood=1)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("Modius1", capacity=8, blood=1)
    _make_modius(p2, "Modius1")
    p2.hand_cards(["Fake Master"], card_type="Master")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")  # attempt_block only ever asks the defender
    defender.expect(POLLING_STEP_HOOK, "modius_discard_master:Modius1")
    defender.expect("polling_step_cast", "for:modius:Modius1:0")
    defender.expect("polling_step_cast", "for:title:Modius1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    result = political_action(game.state, "P1", game.vampire("Caller"))

    assert result is True  # 1 (P1's political action card) + 1 + 2 (Modius's ability + title) for
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == ["Fake Master"]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_modius_is_repeatable_bounded_only_by_master_cards_in_hand():
    """The printed text carries no "(limited)"/"once per referendum" cap:
    with two master cards in hand, the ability is offered, used, and
    discards a card twice in the same pre-cast window, granting two
    separate +1-vote sources."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Modius1", capacity=8, blood=1)
    _make_modius(p1, "Modius1")
    p1.hand_cards(["Fake Master 1", "Fake Master 2"], card_type="Master")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, "modius_discard_master:Modius1")
    actor.expect(POLLING_STEP_HOOK, "modius_discard_master:Modius1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Modius1")
    actor.expect("polling_step_cast", "for:modius:Modius1:0")
    actor.expect("polling_step_cast", "for:modius:Modius1:1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Modius1"))

    assert result is True
    assert game.state.players["P1"].hand == []
    assert sorted(c.name for c in game.state.players["P1"].ash_heap) == [
        "Fake Master 1",
        "Fake Master 2",
    ]
    actor.assert_exhausted()
