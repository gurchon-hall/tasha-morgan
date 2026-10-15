"""Alexa Draper (krcg id 201529, `src/vtesbot/cards/alexa_draper.py`).

Card text: "Camarilla Prince of Melbourne: During the polling step of any
referendum, Alexa can discard a card requiring Dominate [dom] to get +1
vote."

Ruling:
    - "The ability can be used while locked, only once per referendum."
      [ANK 20220705] -- both halves get a dedicated test below (locked-use,
      once-per-referendum cap).

One assertion per clause/behaviour: "discard a card requiring Dominate"
(a Mono-requirement card and, separately, a Choice-requirement card that
merely *includes* Dominate among several options, proving
`requires_discipline`'s membership check either way), a hand card that does
*not* require Dominate is never offered, "+1 vote" (a new castable vote
source), "only once per referendum" (a second qualifying hand card is not
also discarded in the same referendum), and "can be used while locked".
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.alexa_draper import KRCG_ID
from vtesbot.engine import CryptCard, DisciplineRequirement, DisciplineRequirementType
from vtesbot.engine.politics import POLLING_STEP_HOOK, political_action


def _make_alexa(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Alexa Draper's real printed
    identity (`CryptCard` is frozen, mirrors `test_modius.py::_make_modius`'s
    own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name="Alexa Draper",
        capacity=8,
        group=6,
        clan="Ventrue",
        title="Prince",
        disciplines=("for", "pot", "DOM", "PRE"),
    )


def test_registered_as_implemented_against_the_polling_step_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Alexa Draper"
    assert reg.blocked_reason is None


def test_alexa_draper_discards_a_mono_dominate_card_for_1_vote():
    """ "discard a card requiring Dominate [dom]" -- a plain Mono `[dom]`
    requirement qualifies."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Alexa1", capacity=8, blood=1)
    _make_alexa(p1, "Alexa1")
    p1.hand_card(
        "Fake Dom Mono",
        discipline_requirement=DisciplineRequirement(
            type=DisciplineRequirementType.MONO, disciplines=("dom",)
        ),
    )
    builder.player("P2", pool=30)
    game = builder.build()
    card_id = game.state.players["P1"].hand[0].krcg_id
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, f"alexa_draper:0:{card_id}")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Alexa1")
    actor.expect("polling_step_cast", "for:alexa_draper:Alexa1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Alexa1"))

    # 1 (political action card) + 2 (Alexa's own ready Prince title) + 1
    # (Alexa's discard-a-dominate-card ability) for vs 0 against: passes.
    assert result is True
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Fake Dom Mono"]
    assert game.pool_of("P1") == 30  # the cost is a discarded card, never pool
    actor.assert_exhausted()


def test_alexa_draper_discards_a_choice_card_that_includes_dominate():
    """ "discard a card requiring Dominate" -- a Choice-type requirement
    that merely *includes* `dom` among several options (e.g. Line Brawl's
    own shape) also qualifies: `requires_discipline` is a membership check,
    not a type-specific one."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Alexa1", capacity=8, blood=1)
    _make_alexa(p1, "Alexa1")
    p1.hand_card(
        "Fake Dom Choice",
        discipline_requirement=DisciplineRequirement(
            type=DisciplineRequirementType.CHOICE, disciplines=("dom", "for", "pre")
        ),
    )
    builder.player("P2", pool=30)
    game = builder.build()
    card_id = game.state.players["P1"].hand[0].krcg_id
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, f"alexa_draper:0:{card_id}")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Alexa1")
    actor.expect("polling_step_cast", "for:alexa_draper:Alexa1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Alexa1"))

    assert result is True
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Fake Dom Choice"]
    actor.assert_exhausted()


def test_alexa_draper_not_offered_for_a_card_not_requiring_dominate():
    """A hand card whose printed requirement does not include `dom` is
    never offered (proven by omission: no `POLLING_STEP_HOOK` decision is
    scripted, and `ScriptedAgent` fails loudly on any unscripted
    decision)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Alexa1", capacity=8, blood=1)
    _make_alexa(p1, "Alexa1")
    p1.hand_card(
        "Fake Obfuscate Card",
        discipline_requirement=DisciplineRequirement(
            type=DisciplineRequirementType.MONO, disciplines=("obf",)
        ),
    )
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Alexa1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Alexa1"))

    assert result is True
    assert [c.name for c in game.state.players["P1"].hand] == ["Fake Obfuscate Card"]
    assert game.state.players["P1"].ash_heap == []
    actor.assert_exhausted()


def test_alexa_draper_only_once_per_referendum():
    """[ANK 20220705]: "only once per referendum" -- with two qualifying
    Dominate-requiring cards in hand, only one is ever discarded during the
    same referendum; the second stays in hand untouched."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Alexa1", capacity=8, blood=1)
    _make_alexa(p1, "Alexa1")
    p1.hand_card("Dom Card 1", discipline_requirement=DisciplineRequirement(disciplines=("dom",)))
    p1.hand_card("Dom Card 2", discipline_requirement=DisciplineRequirement(disciplines=("dom",)))
    builder.player("P2", pool=30)
    game = builder.build()
    card1_id = game.state.players["P1"].hand[0].krcg_id
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, f"alexa_draper:0:{card1_id}")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Alexa1")
    actor.expect("polling_step_cast", "for:alexa_draper:Alexa1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Alexa1"))

    assert result is True
    assert [c.name for c in game.state.players["P1"].hand] == ["Dom Card 2"]
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Dom Card 1"]
    actor.assert_exhausted()


def test_alexa_draper_usable_while_locked():
    """[ANK 20220705]: "The ability can be used while locked." Alexa sits
    locked (independent of who calls the referendum) the whole time; her
    own generic ready-titled-vampire vote (worth 2, Prince) is unaffected
    by lock state either (Rulebook §4 Politics > Gaining Votes checks only
    `zone == 'ready'`), and her own discard ability still fires despite
    being locked."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Caller", capacity=4, blood=1)
    p1.ready_vampire("Alexa1", capacity=8, blood=1, locked=True)
    _make_alexa(p1, "Alexa1")
    p1.hand_card(
        "Fake Dom Mono", discipline_requirement=DisciplineRequirement(disciplines=("dom",))
    )
    builder.player("P2", pool=30)
    game = builder.build()
    card_id = game.state.players["P1"].hand[0].krcg_id
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, f"alexa_draper:0:{card_id}")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Alexa1")
    actor.expect("polling_step_cast", "for:alexa_draper:Alexa1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Caller"))

    assert result is True
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Fake Dom Mono"]
    actor.assert_exhausted()
