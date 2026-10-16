"""Seduction (krcg id 101712, `src/vtesbot/cards/seduction.py`).

Card text: "Only usable as the action is announced.\n[dom] Choose a
younger vampire. The chosen vampire cannot block this action.\n[DOM] As
above, but choose any vampire."

One assertion per clause/discipline level: the basic clause's `dom` gate,
its "younger vampire" (strictly lower printed capacity) restriction, the
no-eligible-target guard, and its single-vs-multiple-target `Decision`
binding; the superior clause's `DOM` gate and its widened "any vampire"
pool (reaching a same-or-higher-capacity target the basic clause cannot);
both clauses offered together for a superior vampire; the exclusion
actually removing the chosen vampire from a real `attempt_block` decision
end-to-end; and the once-per-action cap (Rulebook §2 Card Types, `rules-
auditor` finding): a second copy cannot exclude a second vampire within
one window, the cap is shared between the basic and superior clauses
(the same named card at different Discipline levels), and it does not
persist into a different action's own `pending` dict.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.seduction import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import (
    BLOCK_CANDIDATE_EXCLUSION_HOOK,
    PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY,
    attempt_block,
)

NAME = "Seduction"


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


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


def test_basic_not_offered_without_dom():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5)
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()

    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending={})
    assert options == []


def test_basic_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("dom",))
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()

    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending={})
    assert options == []


def test_basic_not_offered_without_an_eligible_younger_block_candidate():
    """ "Choose a younger vampire": the opponent's only ready-unlocked
    vampire has capacity >= the acting vampire's -- no legal target, so
    nothing is offered at all (never a vacuous play)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=3, disciplines=("dom",))
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5)
    game = builder.build()

    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending={})
    assert options == []


def test_basic_single_eligible_target_binds_directly_and_excludes_it():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("dom",))
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()

    pending: dict = {}
    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)
    assert {o.choice.value for o in options} == {"seduction:basic"}

    options[0].cost(game.state)
    options[0].apply(game.state)

    assert pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY] == {"B1"}
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


def test_basic_raises_a_decision_with_more_than_one_eligible_younger_target():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("dom",))
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3)
    p2.ready_vampire("B2", capacity=4)
    game = builder.build()

    pending: dict = {}
    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)
    assert {o.choice.value for o in options} == {"seduction:basic"}

    actor = ScriptedAgent("P1")
    actor.expect("seduction_target", "seduction_target:B2")
    game.state.agents["P1"] = actor

    options[0].cost(game.state)
    options[0].apply(game.state)

    assert pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY] == {"B2"}
    actor.assert_exhausted()


def test_basic_excludes_a_target_already_at_or_above_capacity_from_its_own_pool():
    """A second ready-unlocked vampire at or above the acting vampire's
    capacity is simply not among the basic clause's own candidates, even
    though another, younger one is -- proven by it never being offered as
    a choice in the single-target case above, and here by it being
    excluded from a two-candidate pool."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("dom",))
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3)
    p2.ready_vampire("B2", capacity=5)  # not younger: basic cannot reach it.
    game = builder.build()

    pending: dict = {}
    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)
    assert {o.choice.value for o in options} == {"seduction:basic"}

    options[0].cost(game.state)
    options[0].apply(game.state)  # single eligible target (B1): binds directly.

    assert pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY] == {"B1"}


def test_superior_not_offered_with_only_basic_dom():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("dom",))
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()

    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending={})
    assert "seduction:superior" not in {o.choice.value for o in options}


def test_superior_requires_dom_and_widens_to_any_vampire():
    """ "[DOM] As above, but choose any vampire": with superior Dominate,
    a same-capacity target (unreachable by the basic clause) is a legal
    choice."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("DOM",))
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5)
    game = builder.build()

    pending: dict = {}
    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)
    values = {o.choice.value for o in options}
    assert "seduction:superior" in values
    assert "seduction:basic" not in values  # B1 is not younger: basic has no target here.

    superior = next(o for o in options if o.choice.value == "seduction:superior")
    superior.cost(game.state)
    superior.apply(game.state)
    assert pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY] == {"B1"}


def test_superior_vampire_may_choose_either_clause_when_a_younger_target_also_exists():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("DOM",))
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3)
    game = builder.build()

    options = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending={})
    assert {o.choice.value for o in options} == {"seduction:basic", "seduction:superior"}


# --- once-per-action cap (Rulebook §2: "A minion cannot play the same
# action modifier card more than once during a single action (even if
# using a different Discipline level)") --------------------------------


def test_second_copy_cannot_exclude_a_second_vampire_within_one_window():
    """`rules-auditor` finding: two copies of this card in hand previously
    let the actor exclude two different defending vampires in the same
    `BLOCK_CANDIDATE_EXCLUSION_HOOK` window."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("dom",))
    p1.hand.append(_card())
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3)
    p2.ready_vampire("B2", capacity=3)
    game = builder.build()

    pending: dict = {}
    first = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)
    option = next(o for o in first if o.choice.value == "seduction:basic")
    actor = ScriptedAgent("P1")
    actor.expect("seduction_target", "seduction_target:B1")
    game.state.agents["P1"] = actor
    option.cost(game.state)
    option.apply(game.state)

    assert pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY] == {"B1"}
    actor.assert_exhausted()

    second = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)

    assert second == []  # already played this action; B2 is left unexcluded.


def test_basic_and_superior_share_the_same_per_action_cap():
    """ "even if using a different Discipline level": a superior vampire's
    basic-clause play also trips the superior clause's own offer this
    same action."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("DOM",))
    p1.hand.append(_card())
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3)
    p2.ready_vampire("B2", capacity=5)
    game = builder.build()

    pending: dict = {}
    first = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)
    basic = next(o for o in first if o.choice.value == "seduction:basic")
    basic.cost(game.state)
    basic.apply(game.state)  # basic clause's own single eligible target: B1.

    assert pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY] == {"B1"}

    second = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=pending)

    assert second == []  # superior clause's own offer is also capped, not just basic's.


def test_cap_does_not_persist_into_a_different_action():
    """A fresh `pending` dict (a new action) is not capped by a previous
    action's play."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("dom",))
    p1.hand.append(_card())
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3)
    game = builder.build()

    first_pending: dict = {}
    first = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=first_pending)
    first_basic = next(o for o in first if o.choice.value == "seduction:basic")
    first_basic.cost(game.state)
    first_basic.apply(game.state)

    second_pending: dict = {}
    second = _offer(game, actor="P1", defender="P2", acting_vampire="A1", pending=second_pending)

    assert {o.choice.value for o in second} == {"seduction:basic"}


def test_exclusion_removes_the_chosen_vampire_from_a_real_block_attempt():
    """End-to-end through `attempt_block`: B1 is excluded, leaving only
    B2 as a legal block candidate."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("A1", capacity=5, disciplines=("dom",))
    p1.hand.append(_card())
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1)  # younger: Seduction's own target.
    p2.ready_vampire("B2", capacity=5, blood=1)  # not younger: untouched, still a candidate.
    game = builder.build()
    acting = game.vampire("A1")

    actor = ScriptedAgent("P1")
    actor.expect("block_candidate_exclusion", "seduction:basic")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B2")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0, acting_vampire=acting)

    assert blocker is not None
    assert blocker.instance_id == "B2"
    actor.assert_exhausted()
    defender.assert_exhausted()
