"""Kine Resources Contested (krcg id 101056,
`src/vtesbot/cards/kine_resources_contested.py`).

Card text: "Allocate 4 points among two or more Methuselahs. Successful
referendum means each Methuselah burns 1 pool for each point allocated."
Rulings: "Cannot allocate 4 points to a single Methuselah, but you can
allocate points to yourself." [LSJ 20000622]; "If multiple ousts happen,
players whose prey gets ousted get a victory point, even if they are being
ousted themselves. Only the surviving ones get 6 pool from the oust of
their prey (not of their grand-prey)." [LSJ 20000309]; "Can allocate more
points than a Methuselah has pool." [LSJ 20020819].

One assertion per clause/ruling: card-in-hand gating (not offered without
it), the `"action_card_play"` hook wiring through the real `minion_phase`
(happy path: referendum passes, allocation decision, pool burned on both
sides), the referendum failing (no effect at all -- "the referendum fails
and has no effect"), a blocked action (never calls a referendum, card is
still burned either way), the legal-split enumeration derived from "among
two or more Methuselahs" (never 4/0 or 0/4), and "can allocate more points
than a Methuselah has pool" together with the resulting oust (2P's own
"[m]ultiple ousts" ruling is inapplicable here -- there is structurally
only ever one oust event in a duel, per `engine/ousting.py`).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.kine_resources_contested import KRCG_ID
from vtesbot.cards.marcos_belegrad import KRCG_ID as MARCOS_ID
from vtesbot.cards.oxford_university_england import KRCG_ID as OXFORD_ID
from vtesbot.cards.oxford_university_england import NAME as OXFORD_NAME
from vtesbot.cards.registry import Status, get
from vtesbot.engine import CryptCard, LibraryCard, hooks
from vtesbot.engine.action import ACTION_POLITICAL
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.master_cards import bring_master_card_into_play
from vtesbot.engine.phases.minion import minion_phase
from vtesbot.engine.politics import POLLING_STEP_HOOK

NAME = "Kine Resources Contested"


def _kine_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="Political Action")


def test_registered_as_implemented_against_the_action_card_play_hook():
    reg = get(KRCG_ID)
    assert reg is not None
    assert reg.status is Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "action_choice":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["bleed", "hunt"]]
    actor.assert_exhausted()


def test_offered_and_a_passing_referendum_burns_the_chosen_split():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("kine_resources_contested_allocation", "allocate:2")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 28  # 30 - 2
    assert game.pool_of("P2") == 28  # 30 - 2
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_a_referendum_that_fails_has_no_effect():
    """Rulebook SS4 "Resolve the Referendum": "Otherwise, the referendum
    fails and has no effect." An opposing ready Prince's 2 votes outvote the
    caller's lone 1-vote political-action-card source."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Prince")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("kine_resources_contested_allocation", "allocate:2")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 30
    assert game.pool_of("P2") == 30
    assert game.state.players["P1"].hand == []  # the card is still consumed either way
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_blocked_action_never_calls_a_referendum_and_the_card_is_still_burned():
    """Rulebook SS4 "Resolve the Action": a blocked action never reaches the
    referendum at all (OQ-5's verbatim quote, `engine/politics.py`'s own
    module docstring) -- the card is still burned, same destination as an
    unblocked play either way. A temporary fake `"intercept_modifier"`
    provider stands in for some other intercept-granting card so a
    base-stealth-1 action (`POLITICAL_ACTION_STEALTH`) can actually be
    blocked in this test, mirroring `test_enchant_kindred.py`'s own pattern
    for its stealth-1 superior clause."""

    def match_political_stealth(state, context):
        if context.get("action") != ACTION_POLITICAL:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_political_stealth)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
        p1.hand.append(_kine_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "kine_resources_contested:play")
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

        assert game.pool_of("P1") == 30
        assert game.pool_of("P2") == 30
        assert game.state.players["P1"].hand == []
        assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_political_stealth)


def test_allocation_choices_never_let_a_single_methuselah_get_all_four_or_zero():
    """ "Allocate 4 points **among two or more Methuselahs**" requires both
    of the two Methuselahs to receive a nonzero share in a duel (module
    docstring); this directly subsumes the printed ruling "[c]annot allocate
    4 points to a single Methuselah" -- the legal split set offered is
    exactly {1/3, 2/2, 3/1}, never 4/0 or 0/4."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "kine_resources_contested_allocation":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("kine_resources_contested_allocation", "allocate:1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["allocate:1", "allocate:2", "allocate:3"]]
    assert game.pool_of("P1") == 29  # self got 1 point allocated (burns 1 pool)
    assert game.pool_of("P2") == 27  # other got 3 points allocated (burns 3 pool)
    actor.assert_exhausted()


def test_can_allocate_more_points_than_a_methuselah_has_pool_and_it_ousts_them():
    """Ruling: "Can allocate more points than a Methuselah has pool."
    `lose_pool` floors at the player's current pool and still checks
    ousting (`engine/pool.py`) -- driving the opponent's pool to exactly 0
    triggers the ordinary 2P oust path (`engine/ousting.py`, reproducing
    `tests/rules/test_ousting.py::test_pool_at_zero_ousts_and_ends_the_game`'s
    own worked numbers), not a new mechanism this card needs to build."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=2)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("kine_resources_contested_allocation", "allocate:1")  # other gets 3, only has 2
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 0  # floored at 0, not negative
    assert "P2" in game.state.eliminated
    assert game.state.game_over is True
    assert game.state.winner == "P1"
    assert game.state.victory_points["P1"] == 2  # 1 (ousted prey) + 1 (last Methuselah)
    assert game.pool_of("P1") == 35  # 30 - 1 (self-allocated) + 6 (oust bonus)
    actor.assert_exhausted()


def test_oust_at_tally_applies_no_allocation_burn():
    """A tally-time oust (REFERENDUM_TALLIED reaction) ends the game: the
    locked split is never applied (Rulebook SS5)."""
    from vtesbot.engine.pool import lose_pool

    def oust_caller(state, context):
        lose_pool(state, "P1", 30)

    hooks.register("referendum_tallied", oust_caller)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
        p1.hand.append(_kine_card())
        builder.player("P2", pool=30)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "kine_resources_contested:play")
        actor.expect("kine_resources_contested_allocation", "allocate:2")
        actor.expect("polling_step_cast", "for:political_action_card:P1")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = ScriptedAgent("P2")

        minion_phase(game.state, "P1")

        assert game.state.game_over is True
        assert game.pool_of("P2") == 36  # 30 + 6 oust bonus, nothing burned
    finally:
        hooks.unregister("referendum_tallied", oust_caller)


def _action_choices_for_kine_caller(pool: int) -> list[str]:
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=pool).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[str] = []

    class Rec(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "action_choice":
                seen.extend(c.value for c in decision.choices)
            return super().decide(observation, decision)

    actor = Rec("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")
    minion_phase(game.state, "P1")
    return seen


def test_not_offered_when_no_split_can_leave_the_caller_above_zero_pool():
    """OQ-42 (user ruling): the caller picks the split, so the caller's own
    share must leave them 1+ pool; with pool 1 every split (1/3, 2/2, 3/1)
    would self-oust."""
    assert "kine_resources_contested:play" not in _action_choices_for_kine_caller(1)
    assert "kine_resources_contested:play" in _action_choices_for_kine_caller(2)


def test_allocation_never_offers_a_self_share_that_zeroes_the_caller():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=3).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[list[str]] = []

    class Rec(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "kine_resources_contested_allocation":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = Rec("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("kine_resources_contested_allocation", "allocate:2")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["allocate:1", "allocate:2"]]  # pool 3: self share <= 2
    assert game.pool_of("P1") == 1


def test_kine_with_oxford_burn_is_capped_by_the_pool_reserve_and_allocation_stays_legal():
    """`resolve_referendum(pool_reserve={player: 1})` keeps Kine's mandatory
    self share payable: at pool 3 with allocate:1 locked first Oxford may burn only X=1."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=3).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    location = bring_master_card_into_play(game.state, "P1", krcg_id=OXFORD_ID, name=OXFORD_NAME)
    burn_options: list[str] = []

    class Rec(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == POLLING_STEP_HOOK:
                burn_options.extend(c.value for c in decision.choices)
            return super().decide(observation, decision)

    actor = Rec("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("kine_resources_contested_allocation", "allocate:1")
    actor.expect(POLLING_STEP_HOOK, f"oxford:{location.instance_id}:1")
    actor.expect("polling_step_cast", f"for:oxford:{location.instance_id}:1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert [v for v in burn_options if v.startswith("oxford:")] == [
        f"oxford:{location.instance_id}:1"
    ]
    assert game.pool_of("P1") == 1  # 3 - 1 (Oxford) - 1 (allocate:1)
    assert game.pool_of("P2") == 27
    assert game.state.game_over is False
    actor.assert_exhausted()


def test_kine_under_marcos_never_dead_ends_on_the_callers_own_against_vote():
    """Audit repro: P1 (pool 2) acts with Marcos and plays Kine. Voting
    against their own referendum would cost the Marcos burn (pool -> 1, no
    legal split left); OQ-43 (choices leading to own 0 are forbidden) means
    that vote is not offered, so the allocation can no longer dead-end."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=2)
    p1.ready_vampire("Marcos1", capacity=8, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    game.vampire("Marcos1").card = CryptCard(
        krcg_id=MARCOS_ID,
        name="Marcos Belegrad",
        capacity=8,
        group=7,
        clan="Toreador",
        title="Prince",
        disciplines=("ani", "AUS", "CEL", "PRE"),
    )
    offered: list[str] = []

    class Rec(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "polling_step_cast":
                offered.extend(c.value for c in decision.choices)
            return super().decide(observation, decision)

    actor = Rec("P1")
    actor.expect("minion_phase_choice", "act_with:Marcos1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Marcos1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert not any(v.startswith("against:") for v in offered)
    assert game.state.game_over is False
    assert game.pool_of("P1") == 1  # allocate:1 (auto-resolved)
    assert game.pool_of("P2") == 27
    actor.assert_exhausted()


def _marcos_scenario(pool: int, p2_pool: int = 30):
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=pool)
    p1.ready_vampire("Marcos1", capacity=8, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=p2_pool)
    game = builder.build()
    game.vampire("Marcos1").card = CryptCard(
        krcg_id=MARCOS_ID,
        name="Marcos Belegrad",
        capacity=8,
        group=7,
        clan="Toreador",
        title="Prince",
        disciplines=("ani", "AUS", "CEL", "PRE"),
    )
    return game


def test_allocation_is_locked_before_the_first_vote_and_pre_vote_window():
    """User ruling 2026-10-13 (OQ-45): the split is locked before the vote,
    then the pre-vote window, then votes, then end-of-tally reactions, then
    the effects. Rulebook SS4 "The Referendum" step 1 "Choose the terms"
    precedes step 2 "Polling"."""
    log: list[str] = []

    def pre_vote(state, context):
        if context.get("phase") == "before_cast" and (not log or log[-1] != "pre_vote_window"):
            log.append("pre_vote_window")
        return []

    def tallied(state, context):
        log.append("tally_reactions")

    hooks.register(POLLING_STEP_HOOK, pre_vote)
    hooks.register("referendum_tallied", tallied)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
        p1.hand.append(_kine_card())
        builder.player("P2", pool=30)
        game = builder.build()

        class Rec(ScriptedAgent):
            def decide(self, observation, decision):
                log.append(decision.kind)
                if decision.kind == "kine_resources_contested_allocation":
                    assert game.pool_of("P1") == 30 and game.pool_of("P2") == 30
                return super().decide(observation, decision)

        actor = Rec("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "kine_resources_contested:play")
        actor.expect("kine_resources_contested_allocation", "allocate:2")
        actor.expect("polling_step_cast", "for:political_action_card:P1")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = ScriptedAgent("P2")

        minion_phase(game.state, "P1")

        trimmed = [e for e in log if e not in ("minion_phase_choice", "action_choice")]
        assert trimmed[:4] == [
            "kine_resources_contested_allocation",
            "pre_vote_window",
            "polling_step_cast",
            "tally_reactions",
        ]
        assert game.pool_of("P1") == 28 and game.pool_of("P2") == 28
    finally:
        hooks.unregister(POLLING_STEP_HOOK, pre_vote)
        hooks.unregister("referendum_tallied", tallied)


def test_marcos_against_vote_is_withheld_when_the_locked_share_would_become_unpayable():
    """Audit repro (pool 2, Marcos, Kine): with share 1 locked, an against
    vote (tally burn 1) would leave pool 1 < share + 1. Not offered; the
    referendum then resolves legally."""
    game = _marcos_scenario(pool=2)
    offered: list[str] = []

    class Rec(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "polling_step_cast":
                offered.extend(c.value for c in decision.choices)
            return super().decide(observation, decision)

    actor = Rec("P1")
    actor.expect("minion_phase_choice", "act_with:Marcos1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Marcos1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert not any(v.startswith("against:") for v in offered)
    assert game.state.game_over is False
    assert game.pool_of("P1") == 1
    assert game.pool_of("P2") == 27


def test_marcos_against_vote_is_offered_when_pool_covers_tally_burn_and_locked_share():
    """Pool 4, share 1 locked: against costs 1 (Marcos) and share 1 still
    leaves 2 >= 1. With share 3 locked it is withheld (4 - 1 - 3 = 0)."""

    def run(share: int) -> tuple[list[str], int]:
        game = _marcos_scenario(pool=4)
        offered: list[str] = []

        class Rec(ScriptedAgent):
            def decide(self, observation, decision):
                if decision.kind == "polling_step_cast":
                    offered.extend(c.value for c in decision.choices)
                return super().decide(observation, decision)

        actor = Rec("P1")
        actor.expect("minion_phase_choice", "act_with:Marcos1")
        actor.expect("action_choice", "kine_resources_contested:play")
        actor.expect("kine_resources_contested_allocation", f"allocate:{share}")
        direction = "against" if share == 1 else "for"
        actor.expect("polling_step_cast", f"{direction}:political_action_card:P1")
        actor.expect("polling_step_cast", "for:title:Marcos1")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = ScriptedAgent("P2")
        minion_phase(game.state, "P1")
        assert game.state.game_over is False
        return offered, game.pool_of("P1")

    offered, pool = run(1)
    assert "against:political_action_card:P1" in offered
    assert pool == 2  # 4 - 1 (Marcos tally burn) - 1 (locked share)
    offered, _ = run(3)
    assert not any(v.startswith("against:") for v in offered)


def test_locked_share_must_be_affordable_when_locked():
    """Pool 2: only share 1 is lockable (own pool >= share + 1, D-9)."""
    assert [p for p in _legal_self_points_for(2)] == [1]
    assert [p for p in _legal_self_points_for(4)] == [1, 2, 3]


def _legal_self_points_for(pool: int):
    from vtesbot.cards.kine_resources_contested import _legal_self_points

    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=pool)
    builder.player("P2", pool=30)
    return _legal_self_points(builder.build().state, "P1")
