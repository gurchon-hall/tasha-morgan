"""Lucinde, Alastor (krcg id 201700, `src/vtesbot/cards/lucinde_alastor.py`).

Card text: "Camarilla Ventrue Justicar: During your master phase, Lucinde
can burn 1 blood to choose a vampire; this turn, Camarilla vampires you
control can enter combat with the chosen vampire as a Ⓓ action. +1
bleed." Ruling: "The ability can be used when in torpor. [LSJ 20011022]".

One assertion per clause/ruling/judgment call (module docstring for the
full reasoning): registry entry; 2P legality; the ability usable while
Lucinde is in torpor (the on-file ruling); the 1-blood cost; the
once-per-master-phase cap (Rulebook §3 "During X, do Y"); the "choose a
vampire" target pool (opponent's ready *or* torpid vampires, never
uncontrolled -- broader than `line_brawl.py`'s own "Enter combat" target
pool, deliberately, per the module docstring); the target `Decision` with
more than one eligible target; the granted enter-combat option for a
Camarilla vampire, both unblocked and blocked; its absence for a
non-Camarilla vampire; the grant not surviving into a later turn; and the
+1 bleed modifier.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.lucinde_alastor import KRCG_ID
from vtesbot.engine import CryptCard, Sect, hooks
from vtesbot.engine.phases.master import MASTER_PHASE_ABILITY_HOOK, master_phase
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    active_enter_combat_grants,
    minion_phase,
)

NAME = "Lucinde, Alastor"
DISCIPLINES = ("obf", "pot", "tha", "DOM", "FOR", "PRE")


def _make_lucinde(builder_player, instance_id: str, sect: Sect | None = Sect.CAMARILLA) -> None:
    """Swap the just-built vampire's `card` for Lucinde's real printed
    identity (`CryptCard` is frozen, mirrors `test_diana_iadanza.py::
    _make_diana`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=10,
        group=7,
        clan="Ventrue",
        title="Justicar",
        disciplines=DISCIPLINES,
        sect=sect,
    )


def _set_sect(builder_player, instance_id: str, sect: Sect | None) -> None:
    """Mirrors `test_line_brawl.py::_set_sect`."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    old = vampire.card
    vampire.card = CryptCard(
        krcg_id=old.krcg_id,
        name=old.name,
        capacity=old.capacity,
        group=old.group,
        clan=old.clan,
        title=old.title,
        disciplines=old.disciplines,
        sect=sect,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


def test_krcg_confirms_card_text_and_the_torpor_ruling():
    """Uses `krcg.load()`, the installed package's own API (CLAUDE.md §4:
    "verify the API against the installed version before relying on
    it") -- same pattern as `test_alice_chen.py::
    test_krcg_confirms_the_title_and_no_other_clause`."""
    import krcg

    card = krcg.load()[KRCG_ID]
    assert card.text == (
        "Camarilla Ventrue Justicar: During your master phase, Lucinde can "
        "burn 1 blood to choose a vampire; this turn, Camarilla vampires "
        "you control can enter combat with the chosen vampire as a Ⓓ "
        "action. +1 bleed."
    )
    assert card.capacity == 10
    assert card.group.value == "G7"  # krcg's own `Group` enum, group 7
    assert any("used when in torpor" in r.text for r in card.rulings)


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


# --- "During your master phase, Lucinde can burn 1 blood to choose a -------
# --- vampire" ----------------------------------------------------------------


def test_ability_usable_while_lucinde_is_in_torpor():
    """On-file ruling [LSJ 20011022]: usable even though Lucinde herself is
    in torpor, so not gated on `is_ready_unlocked`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.torpid_vampire("Lucinde1", capacity=10, blood=1)
    _make_lucinde(p1, "Lucinde1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    assert game.vampire("Lucinde1").zone == "torpor"
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "lucinde_alastor_ability:Lucinde1")
    # No second decision: with an empty hand and the ability now capped for
    # this turn, `master_phase` has nothing left to offer and returns
    # without a vacuous "pass" (`engine/phases/master.py`'s own "nothing
    # legal to play or activate" early return).
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()
    assert game.blood_of("Lucinde1") == 0  # 1 blood burned, per the printed cost
    grants = active_enter_combat_grants(game.state, "P1")
    assert len(grants) == 1
    assert grants[0].target_vampire_id == game.vampire("B1").instance_id


def test_ability_not_offered_without_1_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=0)
    _make_lucinde(p1, "Lucinde1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(MASTER_PHASE_ABILITY_HOOK, game.state, player="P1")

    assert options == []


def test_ability_not_offered_without_an_eligible_opponent_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=1)
    _make_lucinde(p1, "Lucinde1")
    builder.player("P2", pool=30)  # no vampire at all to choose
    game = builder.build()

    options = hooks.offer(MASTER_PHASE_ABILITY_HOOK, game.state, player="P1")

    assert options == []


def test_ability_capped_at_once_per_master_phase():
    """Rulebook §3 "During X, do Y": at most one activation per master
    phase, even with blood and an eligible target still available.
    Exercised directly against the hook (bypassing `master_phase`'s own
    loop, which would otherwise return with no second decision at all once
    both `master_phase_play` and the now-capped ability have nothing left
    to offer -- see `test_ability_usable_while_lucinde_is_in_torpor`)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=2)
    _make_lucinde(p1, "Lucinde1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    (option,) = hooks.offer(MASTER_PHASE_ABILITY_HOOK, game.state, player="P1")
    option.apply(game.state)

    assert game.blood_of("Lucinde1") == 1  # only 1 of the 2 blood burned
    options_again = hooks.offer(MASTER_PHASE_ABILITY_HOOK, game.state, player="P1")
    assert options_again == []  # not offered again this same master phase


def test_choose_a_vampire_target_pool_includes_a_torpid_opponent_vampire():
    """Deliberately broader than `line_brawl.py`'s own "Enter combat"
    target pool: a torpid opponent vampire is still a legal choice here
    (module docstring, Rulebook §8 "Target")."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=1)
    _make_lucinde(p1, "Lucinde1")
    builder.player("P2", pool=30).torpid_vampire("T1", capacity=3, blood=0)
    game = builder.build()

    (option,) = hooks.offer(MASTER_PHASE_ABILITY_HOOK, game.state, player="P1")
    option.apply(game.state)  # single eligible target: bound directly, no Decision.

    grants = active_enter_combat_grants(game.state, "P1")
    assert len(grants) == 1
    assert grants[0].target_vampire_id == game.vampire("T1").instance_id


def test_choose_a_vampire_excludes_an_uncontrolled_opponent_vampire():
    """An opponent's face-down, uncontrolled vampire is never a legal
    choice (Rulebook §8 "Target": must be "in play")."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=1)
    _make_lucinde(p1, "Lucinde1")
    p2 = builder.player("P2", pool=30)
    p2.torpid_vampire("T1", capacity=3, blood=0)
    p2.uncontrolled_vampire("U1", capacity=3, blood=0)
    game = builder.build()

    (option,) = hooks.offer(MASTER_PHASE_ABILITY_HOOK, game.state, player="P1")
    option.apply(game.state)  # still only 1 eligible target (T1): bound directly.

    grants = active_enter_combat_grants(game.state, "P1")
    assert len(grants) == 1
    assert grants[0].target_vampire_id == game.vampire("T1").instance_id


def test_choose_a_vampire_with_multiple_eligible_targets_raises_a_decision():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=1)
    _make_lucinde(p1, "Lucinde1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0).ready_vampire(
        "B2", capacity=3, blood=0
    )
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "lucinde_alastor_target":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    agent = RecordingAgent("P1")
    agent.expect("master_phase_action", "lucinde_alastor_ability:Lucinde1")
    agent.expect("lucinde_alastor_target", "lucinde_alastor_target:B1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()
    assert seen == [["lucinde_alastor_target:B1", "lucinde_alastor_target:B2"]]
    grants = active_enter_combat_grants(game.state, "P1")
    assert grants[0].target_vampire_id == game.vampire("B1").instance_id


# --- "Camarilla vampires you control can enter combat with the chosen ------
# --- vampire as a Ⓓ action" --------------------------------------------------


def test_camarilla_vampire_uses_the_grant_unblocked():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=2)
    _make_lucinde(p1, "Lucinde1")
    p1.ready_vampire("V1", capacity=6, blood=1)
    _set_sect(p1, "V1", Sect.CAMARILLA)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    master_agent = ScriptedAgent("P1")
    master_agent.expect("master_phase_action", "lucinde_alastor_ability:Lucinde1")
    game.state.agents["P1"] = master_agent
    master_phase(game.state, "P1")
    master_agent.assert_exhausted()

    target_id = game.vampire("B1").instance_id
    granted_value = f"lucinde_alastor_enter_combat:{game.vampire('V1').instance_id}:{target_id}"

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", granted_value)
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    actor.expect("minion_phase_choice", "end_minion_phase")  # Lucinde stays ready/unlocked
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.zone_of("B1") == "ready"  # forced into combat, never locked by this clause
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_camarilla_vampire_blocked_goes_through_the_generic_combat_path():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=2)
    _make_lucinde(p1, "Lucinde1")
    p1.ready_vampire("V1", capacity=6, blood=1)
    _set_sect(p1, "V1", Sect.CAMARILLA)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    master_agent = ScriptedAgent("P1")
    master_agent.expect("master_phase_action", "lucinde_alastor_ability:Lucinde1")
    game.state.agents["P1"] = master_agent
    master_phase(game.state, "P1")
    master_agent.assert_exhausted()

    target_id = game.vampire("B1").instance_id
    granted_value = f"lucinde_alastor_enter_combat:{game.vampire('V1').instance_id}:{target_id}"

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", granted_value)
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    actor.expect("minion_phase_choice", "end_minion_phase")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.vampire("B1").locked is True  # the generic block path's own blocker lock
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_non_camarilla_vampire_does_not_get_the_grant_option():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=2)
    _make_lucinde(p1, "Lucinde1")
    p1.ready_vampire("V1", capacity=6, blood=1)
    _set_sect(p1, "V1", Sect.ANARCH)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "lucinde_alastor_ability:Lucinde1")
    game.state.agents["P1"] = agent
    master_phase(game.state, "P1")
    agent.assert_exhausted()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert options == []


def test_grant_does_not_survive_into_a_later_turn():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=2)
    _make_lucinde(p1, "Lucinde1")
    p1.ready_vampire("V1", capacity=6, blood=1)
    _set_sect(p1, "V1", Sect.CAMARILLA)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "lucinde_alastor_ability:Lucinde1")
    game.state.agents["P1"] = agent
    master_phase(game.state, "P1")
    agent.assert_exhausted()
    assert len(active_enter_combat_grants(game.state, "P1")) == 1

    game.state.turn_number += 1  # simulate the turn having advanced

    assert active_enter_combat_grants(game.state, "P1") == []
    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


# --- "+1 bleed" --------------------------------------------------------------


def test_plus_1_bleed_when_lucinde_herself_bleeds():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=1)
    _make_lucinde(p1, "Lucinde1")
    builder.player("P2", pool=30).ready_vampire("D", capacity=3, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:Lucinde1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base bleed 1 + Lucinde's own +1
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_no_bleed_bonus_when_a_different_vampire_bleeds():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Lucinde1", capacity=10, blood=1, locked=True)  # already acted this turn
    _make_lucinde(p1, "Lucinde1")
    p1.ready_vampire("Other1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("D", capacity=3, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:Other1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed 1 only, Lucinde did not act
    actor.assert_exhausted()
    defender.assert_exhausted()
