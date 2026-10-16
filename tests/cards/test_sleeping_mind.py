"""The Sleeping Mind (krcg id 101805, `src/vtesbot/cards/sleeping_mind.py`).

Card text: "Only usable as the action is announced.\n[dom] Choose a
locked vampire. The chosen vampire cannot block this action.\n[DOM]
During this action, minions cannot unlock."

One assertion per basic-clause qualifier: the `dom` gate, the 1-blood
cost gate (both "cannot afford" and "burned on play"), the "a locked
vampire" target pool (explicitly excluding a ready-unlocked one, unlike
Seduction's own pool), the no-eligible-target guard, single-vs-multiple
target binding, and the exclusion surviving a `WAKE_LOCKED_MINION_HOOK`
wake (the ruling the basic clause's own existence turns on,
[PIB 20150703]) through a real `attempt_block` call; and the once-per-
action cap (Rulebook §2 Card Types, `rules-auditor` finding): a second
copy cannot exclude a second vampire within one window, and the cap does
not persist into a different action's own `pending` dict. The superior
clause is out of scope (module docstring) -- its own absence from the
registered hooks is the only assertion needed for it.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.sleeping_mind import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import (
    BLOCK_CANDIDATE_EXCLUSION_HOOK,
    PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY,
    WAKE_LOCKED_MINION_HOOK,
    attempt_block,
)
from vtesbot.engine.decision import Choice

NAME = "Sleeping Mind, The"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="action modifier")


def _offer(game, *, actor, defender, acting_vampire, pending=None, base_stealth=0):
    return hooks.offer(
        BLOCK_CANDIDATE_EXCLUSION_HOOK,
        game.state,
        player=actor,
        actor=actor,
        defender=defender,
        acting_vampire=acting_vampire,
        action=None,
        directed=None,
        base_stealth=base_stealth,
        pending=pending,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert registry.Hook.BLOCK_CANDIDATE_EXCLUSION in reg.hooks


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


def test_not_offered_without_dom():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=1)
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()

    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending={})
    assert options == []


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, blood=1, disciplines=("dom",))
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()

    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending={})
    assert options == []


def test_not_offered_when_the_acting_vampire_cannot_afford_the_blood_cost():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "A1", capacity=5, blood=0, disciplines=("dom",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()

    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending={})
    assert options == []


def test_not_offered_without_an_eligible_locked_target():
    """ "Choose a locked vampire": a ready-unlocked opponent vampire is
    not a legal target for this clause (unlike Seduction's own pool)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "A1", capacity=5, blood=1, disciplines=("dom",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)  # unlocked.
    game = builder.build()

    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending={})
    assert options == []


def test_single_eligible_locked_target_binds_directly_burns_blood_and_excludes_it():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "A1", capacity=5, blood=1, disciplines=("dom",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()

    pending: dict = {}
    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)
    assert {o.choice.value for o in options} == {"sleeping_mind:basic"}

    options[0].cost(game.state)
    options[0].apply(game.state)

    assert pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY] == {"B1"}
    assert game.vampire("A1").blood == 0  # the printed 1-blood cost, burned on play.
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


def test_raises_a_decision_with_more_than_one_eligible_locked_target():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "A1", capacity=5, blood=1, disciplines=("dom",)
    )
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, locked=True)
    p2.ready_vampire("B2", capacity=3, locked=True)
    game = builder.build()

    pending: dict = {}
    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)
    assert {o.choice.value for o in options} == {"sleeping_mind:basic"}

    actor = ScriptedAgent("P1")
    actor.expect("sleeping_mind_target", "sleeping_mind_target:B2")
    game.state.agents["P1"] = actor

    options[0].cost(game.state)
    options[0].apply(game.state)

    assert pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY] == {"B2"}
    actor.assert_exhausted()


# --- once-per-action cap (Rulebook §2: "A minion cannot play the same
# action modifier card more than once during a single action") ------------


def test_second_copy_cannot_exclude_a_second_vampire_within_one_window():
    """`rules-auditor` finding: two copies of this card in hand previously
    let the actor exclude two different locked defending vampires in the
    same `BLOCK_CANDIDATE_EXCLUSION_HOOK` window."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "A1", capacity=5, blood=2, disciplines=("dom",)
    )
    p1.hand.append(_card())
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, locked=True)
    p2.ready_vampire("B2", capacity=3, locked=True)
    game = builder.build()

    pending: dict = {}
    first = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)
    option = next(o for o in first if o.choice.value == "sleeping_mind:basic")
    actor = ScriptedAgent("P1")
    actor.expect("sleeping_mind_target", "sleeping_mind_target:B1")
    game.state.agents["P1"] = actor
    option.cost(game.state)
    option.apply(game.state)

    assert pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY] == {"B1"}
    actor.assert_exhausted()

    second = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)

    assert second == []  # already played this action; B2 is left unexcluded.


def test_cap_does_not_persist_into_a_different_action():
    """A fresh `pending` dict (a new action) is not capped by a previous
    action's play."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "A1", capacity=5, blood=2, disciplines=("dom",)
    )
    p1.hand.append(_card())
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()

    first_pending: dict = {}
    first = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=first_pending)
    first_basic = next(o for o in first if o.choice.value == "sleeping_mind:basic")
    first_basic.cost(game.state)
    first_basic.apply(game.state)

    second_pending: dict = {}
    second = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=second_pending)

    assert {o.choice.value for o in second} == {"sleeping_mind:basic"}


def test_exclusion_survives_a_later_wake_against_the_same_locked_vampire():
    """[PIB 20150703]: a wake effect still "wakes" the named vampire
    (`woken = True`), but the exclusion -- checked after
    `WAKE_LOCKED_MINION_HOOK` on every pass of `attempt_block`'s retry
    loop -- still vetoes it as a block candidate for the rest of the
    action."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "A1", capacity=5, blood=1, disciplines=("dom",)
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()
    acting = game.vampire("A1")

    def wake_provider(state, context):
        if context["player"] != "P2":
            return []
        b1 = state.players["P2"].vampires["B1"]
        if b1.woken:
            return []

        def apply(s):
            del s
            b1.woken = True

        return [hooks.HookOption(choice=Choice("wake_b1", "Wake B1"), apply=apply)]

    hooks.register(WAKE_LOCKED_MINION_HOOK, wake_provider)
    try:
        actor = ScriptedAgent("P1")
        actor.expect("block_candidate_exclusion", "sleeping_mind:basic")
        game.state.agents["P1"] = actor
        defender = ScriptedAgent("P2")
        defender.expect("wake_locked_minion", "wake_b1")
        game.state.agents["P2"] = defender

        blocker = attempt_block(game.state, "P1", "P2", base_stealth=0, acting_vampire=acting)

        assert blocker is None  # excluded despite being woken: no candidate at all.
        assert game.vampire("B1").woken is True  # the wake itself still happened.
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister(WAKE_LOCKED_MINION_HOOK, wake_provider)


def test_superior_clause_is_not_implemented():
    """Module docstring: no generic mid-action unlock gate exists yet, so
    only the basic clause is registered."""
    from vtesbot.cards import sleeping_mind

    assert not hasattr(sleeping_mind, "_provide_sleeping_mind_superior")
