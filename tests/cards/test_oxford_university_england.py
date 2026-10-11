"""Oxford University, England (krcg id 101341, `src/vtesbot/cards/
oxford_university_england.py`).

Card text: "Unique location.\nYou can lock this card and burn X pool
during the polling step of a political action to get +2X votes." No
rulings on file.

Was `blocked` with a stale `blocked_reason="OQ-6"`; the real remaining
blocker, OQ-23 ("No standalone master-card entity"), is now resolved and
independently `rules-auditor`-reviewed clean.

One assertion per clause/behaviour: the clan-gated master-phase play
("Unique location.", via the now-generic `MasterCardInPlay`/
`bring_master_card_into_play`/`detect_contest_on_bring_into_play`), and the
repeatable lock-and-burn-X-pool-for-votes ability, scoped to this
instance's own controller, only while unlocked and in play, and unlocked
again on the controller's own next unlock phase.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.oxford_university_england import KRCG_ID, NAME
from vtesbot.engine import CryptCard, LibraryCard, hooks
from vtesbot.engine.master_cards import (
    bring_master_card_into_play,
    detect_contest_on_bring_into_play,
)
from vtesbot.engine.phases.master import master_phase
from vtesbot.engine.phases.unlock import unlock_phase
from vtesbot.engine.politics import POLLING_STEP_HOOK, political_action


def _oxford_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="master")


def _set_clan(builder_player, instance_id: str, clan: str | None) -> None:
    """Replace the just-built vampire's `card` with one carrying `clan`
    (`ready_vampire`/`torpid_vampire` have no `clan=` parameter of their
    own -- `CryptCard` is frozen, so a fresh instance is swapped in instead
    of mutated; mirrors `tests/cards/test_forty_seventh_street_royals.py::
    _set_clan` exactly)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    old = vampire.card
    vampire.card = CryptCard(
        krcg_id=old.krcg_id,
        name=old.name,
        capacity=old.capacity,
        group=old.group,
        clan=clan,
        disciplines=old.disciplines,
    )


def test_registered_as_implemented_against_its_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert set(reg.hooks) == {
        registry.Hook.MASTER_PHASE_PLAY,
        registry.Hook.POLLING_STEP,
    }


# --- Clause: "Unique location." (master-phase play, clan requirement) ------


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    _set_clan(p1, "V1", "Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_without_controlling_any_ready_brujah():
    """Rulebook SS2 Card Types > "Requirements for Playing Cards": "only a
    Methuselah who controls a ready minion who meets the requirements of a
    master card can play it" -- a ready vampire of a *different* clan does
    not meet Oxford's own printed Brujah requirement."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    _set_clan(p1, "V1", "Toreador")
    p1.hand.append(_oxford_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_with_only_a_torpid_brujah():
    """A torpid vampire is not in the ready region -- does not satisfy
    "controls a ready minion who meets the requirements"."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_oxford_card())
    p1.torpid_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_when_only_the_opponent_controls_a_ready_brujah():
    """The requirement is "a Methuselah who controls" -- the opponent's own
    ready Brujah does not help this player meet the requirement."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_oxford_card())
    p2 = builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    _set_clan(p2, "V2", "Brujah")
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_a_locked_ready_brujah_still_satisfies_the_requirement():
    """ "Ready" is the only gate (the Ready Region, Rulebook SS8 glossary) --
    whether that vampire happens to be locked or unlocked is irrelevant to
    satisfying a master card's own clan requirement, mirroring
    `engine/politics.py`'s own "locked or unlocked does not have any impact"
    convention for titled-vampire votes."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, locked=True)
    _set_clan(p1, "V1", "Brujah")
    p1.hand.append(_oxford_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "oxford_university_england")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert len(game.state.players["P1"].master_cards) == 1
    agent.assert_exhausted()


def test_playing_it_brings_a_card_into_play_unlocked():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    _set_clan(p1, "V1", "Brujah")
    p1.hand.append(_oxford_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "oxford_university_england")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    card = next(iter(game.state.players["P1"].master_cards.values()))
    assert card.krcg_id == KRCG_ID
    assert card.controller == "P1"
    assert card.zone == "in_play"
    assert card.locked is False
    agent.assert_exhausted()


def test_is_not_a_trifle_no_bonus_master_phase_action():
    """Not printed "Trifle." -- a second copy still in hand after the first
    is played must not be offered as a bonus action (mirrors `tests/cards/
    test_life_in_the_city.py`'s own trifle test, inverted: scripting only
    one answer and asserting the agent's script is fully exhausted proves
    no second decision was ever raised)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    _set_clan(p1, "V1", "Brujah")
    p1.hand.append(_oxford_card())
    p1.hand.append(_oxford_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "oxford_university_england")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert len(game.state.players["P1"].hand) == 1  # the second copy, unplayed
    assert len(game.state.players["P1"].master_cards) == 1
    agent.assert_exhausted()


def test_a_second_independently_played_copy_triggers_a_contest_with_no_oxford_specific_code():
    """ "Unique" governs contest, not initial legality to play -- built
    entirely on the generic OQ-23 Contested-Cards machinery with no
    Oxford-specific contest code, mirroring `tests/cards/test_fame.py`'s
    own analogous test."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    _set_clan(p1, "V1", "Brujah")
    p1.hand.append(_oxford_card())
    builder.player("P2", pool=30)
    game = builder.build()
    existing = bring_master_card_into_play(game.state, "P2", krcg_id=KRCG_ID, name=NAME)

    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "oxford_university_england")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    incoming = next(iter(game.state.players["P1"].master_cards.values()))
    assert incoming.zone == "contested"
    assert existing.zone == "contested"
    assert incoming.contested_with == existing.instance_id
    assert existing.contested_with == incoming.instance_id
    agent.assert_exhausted()


# --- Clause: "You can lock this card and burn X pool during the polling
# step of a political action to get +2X votes." -----------------------------


def test_offers_one_option_per_legal_pool_burn_amount_during_the_polling_step():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=3)
    builder.player("P2", pool=30)
    game = builder.build()
    location = bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        pending={"extra_sources": []},
    )

    assert [o.choice.value for o in options] == [
        f"oxford:{location.instance_id}:1",
        f"oxford:{location.instance_id}:2",
        f"oxford:{location.instance_id}:3",
    ]


def test_not_offered_to_the_opponent_of_the_controller():
    """ "You can lock this card" -- Oxford is its own controller's political
    resource, not a shared one."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=3)
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P2",
        phase="before_cast",
        pending={"extra_sources": []},
    )

    assert options == []


def test_not_offered_while_contested():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=3)
    builder.player("P2", pool=30)
    game = builder.build()
    existing = bring_master_card_into_play(game.state, "P2", krcg_id=KRCG_ID, name=NAME)
    incoming = bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    detect_contest_on_bring_into_play(game.state, incoming)
    assert existing.zone == "contested"

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        pending={"extra_sources": []},
    )

    assert options == []


def test_lock_and_burn_pool_ability_fires_during_a_real_political_actions_polling_step():
    """End-to-end through the real `political_action`, mirroring
    `tests/rules/test_politics.py::
    test_oxford_shaped_polling_step_provider_end_to_end_adds_scaled_votes_and_locks_the_location`'s
    own fake-provider test, now against the real card module: burns the
    chosen amount of pool, adds `2 * X` votes to the tally, and locks the
    card as the ability's own additional cost."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=3).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    location = bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)

    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, f"oxford:{location.instance_id}:2")
    actor.expect("polling_step_cast", f"for:oxford:{location.instance_id}:2")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")  # no ready vampire: no block attempt raised

    result = political_action(game.state, "P1", game.vampire("V1"))

    # 4 (burn 2 pool * 2 votes) + 1 (political action card) for vs 0 against.
    assert result is True
    assert game.state.players["P1"].pool == 1  # 3 - 2 burned
    assert location.locked is True
    actor.assert_exhausted()


def test_an_already_locked_card_is_not_offered_the_ability_again():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=3).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    location = bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    location.locked = True

    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("V1"))

    assert result is True
    assert game.state.players["P1"].pool == 3  # untouched: no option was ever offered
    actor.assert_exhausted()


def test_the_card_unlocks_again_on_its_controllers_next_unlock_phase():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    location = bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    location.locked = True
    game.state.agents["P1"] = ScriptedAgent("P1")  # no decisions expected

    unlock_phase(game.state, "P1")

    assert location.locked is False
    assert location.zone == "in_play"
