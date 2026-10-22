"""Scalpel Tongue (krcg id 101686, `src/vtesbot/cards/scalpel_tongue.py`).

Card text: "Only usable during the polling step of a political action.
[cel][pre] Choose a vampire who has cast votes or ballots in this
referendum. The chosen vampire is locked and abstains (this cancels the
chosen vampire's votes and ballots). [CEL][PRE] As above, and the chosen
vampire burns 1 blood." Ruling: "Cannot be used during a referendum that is
automatically passing." [PIB 20150105] [LSJ 19980107].

One assertion per clause/qualifier/ruling: the combo (both-Disciplines)
gating for each clause, card-in-hand gating, the `"mid_cast"`-phase-only
offer (never `"before_cast"`), narrowing to `"title:"`-sourced casts only
(a political-action-card/Edge source is never offered as a target), the
lock+cancel effect (basic clause) through a real `resolve_referendum` call,
the superior clause's extra "burns 1 blood" (floored at 0), RUL-010's
(resolved) asymmetric "who may play it" -- the caller only through their own
acting vampire (even while it is already locked), the non-caller through any
ready/unlocked qualifying vampire of their own (the pre-existing Reaction-rule
check) -- and the user ruling that a target may already be locked when
chosen, remaining locked afterwards with no special handling. The
"automatically passing" ruling is not independently tested: this engine has
no automatically-passing mechanism to reach it (module docstring RUL-005).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.registry import Status, get
from vtesbot.cards.scalpel_tongue import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.politics import POLLING_STEP_HOOK, resolve_referendum

NAME = "Scalpel Tongue"


def _st_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="Action Modifier")


def _offer(state, player, casts, **extra):
    return hooks.offer(
        POLLING_STEP_HOOK,
        state,
        player=player,
        phase="mid_cast",
        caller=extra.pop("caller", player),
        caller_vampire_id=extra.pop("caller_vampire_id", None),
        other=extra.pop("other", "P2" if player == "P1" else "P1"),
        votes_for=extra.pop("votes_for", 0),
        votes_against=extra.pop("votes_against", 0),
        casts=casts,
        pending=extra.pop("pending", {}),
    )


def test_registered_as_implemented():
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


# --- gating -----------------------------------------------------------------


def test_not_offered_outside_the_mid_cast_phase():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("cel", "pre")
    )
    p1.hand.append(_st_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    game = builder.build()

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id="V1",
        pending={"extra_sources": [], "forced_abstain": set()},
    )

    assert options == []


def test_basic_not_offered_without_both_disciplines():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1",
        capacity=5,
        blood=1,
        disciplines=("cel",),  # missing pre
    )
    p1.hand.append(_st_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    game = builder.build()
    casts = [("P2", "title:B1", 1, "against")]

    options = _offer(game.state, "P1", casts, caller_vampire_id="V1")

    assert options == []


def test_basic_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("cel", "pre")
    )
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    game = builder.build()
    casts = [("P2", "title:B1", 1, "against")]

    options = _offer(game.state, "P1", casts, caller_vampire_id="V1")

    assert options == []


def test_only_title_sourced_casts_are_offered_as_targets():
    """A `political_action_card`/`edge` source is tied to a Methuselah, not
    a specific vampire -- never offered as a target (module docstring)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("cel", "pre")
    )
    p1.hand.append(_st_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    game = builder.build()
    casts = [
        ("P2", "political_action_card_hand:P2", 1, "against"),
        ("P2", "edge:P2", 1, "against"),
        ("P2", "title:B1", 1, "against"),
    ]

    options = _offer(game.state, "P1", casts, caller_vampire_id="V1")

    assert {o.choice.value for o in options} == {"scalpel_tongue:basic:title:B1"}


def test_basic_not_offered_through_a_locked_playing_vampire():
    """`rules-auditor` finding: the *non-caller's* own Reaction-rule check
    requires their playing vampire be ready and unlocked -- contra the
    Rulebook glossary's "a ready unlocked minion can play a reaction card".
    `caller="P2"` forces P1 onto this Reaction-rule path rather than the
    caller-side Action-Modifier path (RUL-010), which does not check `locked`
    at all (see `test_caller_may_play_through_their_own_locked_acting_
    vampire` below)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("cel", "pre")
    )
    p1.vampires[-1].locked = True
    p1.hand.append(_st_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    game = builder.build()
    casts = [("P2", "title:B1", 1, "against")]

    options = _offer(game.state, "P1", casts, caller="P2", other="P1")

    assert options == []


def test_offered_to_either_player_independent_of_caller_role():
    """P1 (the caller) has no `caller_vampire_id` resolving to a qualifying
    vampire here (not passed -- defaults to `None`), so the caller-side
    Action-Modifier path (RUL-010) offers nothing; P2 (the non-caller) is
    unaffected, since their own use is governed by the Reaction rule
    instead, independent of caller role."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1, title="Primogen")
    p2 = builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=5, blood=1, disciplines=("cel", "pre")
    )
    p2.hand.append(_st_card())
    game = builder.build()
    casts = [("P1", "title:V1", 1, "for")]

    p1_options = _offer(game.state, "P1", casts, caller="P1", other="P2")
    p2_options = _offer(game.state, "P2", casts, caller="P1", other="P2")

    assert p1_options == []
    assert {o.choice.value for o in p2_options} == {"scalpel_tongue:basic:title:V1"}


# --- RUL-010 (resolved): caller-side use is pinned to the acting vampire -----


def test_caller_may_play_through_their_own_locked_acting_vampire():
    """The caller's own acting vampire is *always* already locked by the
    time the polling step is reached (Rulebook §4) -- the Action-Modifier
    default does not require it be unlocked, unlike the non-caller's own
    Reaction-rule check."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("cel", "pre")
    )
    p1.vampires[-1].locked = True
    p1.hand.append(_st_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    game = builder.build()
    casts = [("P2", "title:B1", 1, "against")]

    options = _offer(game.state, "P1", casts, caller="P1", other="P2", caller_vampire_id="V1")

    assert {o.choice.value for o in options} == {"scalpel_tongue:basic:title:B1"}


def test_caller_may_not_play_through_a_different_vampire_they_control():
    """A different ready/unlocked [cel][pre] vampire the caller also
    controls, but which is not `caller_vampire_id`, may not play the
    caller-side half -- only the acting vampire itself qualifies."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=1, disciplines=())  # the acting vampire
    p1.ready_vampire("V2", capacity=5, blood=1, disciplines=("cel", "pre"))  # not acting
    p1.hand.append(_st_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    game = builder.build()
    casts = [("P2", "title:B1", 1, "against")]

    options = _offer(game.state, "P1", casts, caller="P1", other="P2", caller_vampire_id="V1")

    assert options == []


# --- "[cel][pre] ... locked and abstains (cancels votes and ballots)." -----


def test_basic_locks_the_target_and_cancels_their_vote_via_a_real_referendum():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    p2 = builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    p2.ready_vampire("B2", capacity=5, blood=1, disciplines=("cel", "pre"))
    p2.hand.append(_st_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")
    defender.expect("polling_step_cast", "against:title:B1")
    defender.expect("polling_step_cast", "scalpel_tongue:basic:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    votes_for, votes_against, casts = resolve_referendum(game.state, "P1", "P2", game.vampire("V1"))

    assert (votes_for, votes_against) == (1, 0)  # B1's -1 against was undone
    assert all(source_id != "title:B1" for (_p, source_id, _v, _d) in casts)
    assert game.vampire("B1").locked is True
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]
    assert game.vampire("B1").blood == 1  # basic clause: no blood burn
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_may_target_an_already_locked_vampire_and_leaves_it_locked():
    """User ruling: "Choose a vampire who has cast votes or ballots" does
    not require the target currently be *unlocked* -- `VampireInPlay.locked`
    is irrelevant to voting (`engine/politics.py`'s own convention), so a
    vampire that voted while already locked (e.g. it had already performed
    its own action earlier this turn) is a legal target. `apply`'s own
    `vampire.locked = True` is simply idempotent: the vampire was locked, is
    chosen, and remains locked."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("cel", "pre")
    )
    p1.hand.append(_st_card())
    p2 = builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    game = builder.build()
    p2.vampires[0].locked = True  # already locked before casting its title vote
    casts = [("P2", "title:B1", 1, "against")]

    options = _offer(game.state, "P1", casts, caller="P2", other="P1")
    option = next(o for o in options if o.choice.value == "scalpel_tongue:basic:title:B1")
    option.apply(game.state)

    assert game.vampire("B1").locked is True  # unchanged: was locked, stays locked


# --- "[CEL][PRE] As above, and the chosen vampire burns 1 blood." ---------


def test_superior_requires_superior_level_of_both_disciplines():
    """Basic `cel` plus superior `PRE` does not unlock the superior clause
    -- both must be at the superior level together (`combo == True`)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("cel", "PRE")
    )
    p1.hand.append(_st_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    game = builder.build()
    casts = [("P2", "title:B1", 1, "against")]

    options = _offer(game.state, "P1", casts, caller_vampire_id="V1")

    assert {o.choice.value for o in options} == {"scalpel_tongue:basic:title:B1"}


def test_superior_offered_with_both_disciplines_at_superior_level():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("CEL", "PRE")
    )
    p1.hand.append(_st_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Primogen")
    game = builder.build()
    casts = [("P2", "title:B1", 1, "against")]

    options = _offer(game.state, "P1", casts, caller_vampire_id="V1")

    assert {o.choice.value for o in options} == {
        "scalpel_tongue:basic:title:B1",
        "scalpel_tongue:superior:title:B1",
    }


def test_superior_burns_one_blood_from_the_target():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("CEL", "PRE")
    )
    p1.hand.append(_st_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=2, title="Primogen")
    game = builder.build()
    casts = [("P2", "title:B1", 1, "against")]

    options = _offer(game.state, "P1", casts, caller_vampire_id="V1")
    option = next(o for o in options if o.choice.value == "scalpel_tongue:superior:title:B1")
    option.apply(game.state)

    assert game.vampire("B1").locked is True
    assert game.vampire("B1").blood == 1


def test_superior_burn_is_floored_at_zero_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("CEL", "PRE")
    )
    p1.hand.append(_st_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, title="Primogen")
    game = builder.build()
    casts = [("P2", "title:B1", 1, "against")]

    options = _offer(game.state, "P1", casts, caller_vampire_id="V1")
    option = next(o for o in options if o.choice.value == "scalpel_tongue:superior:title:B1")
    option.apply(game.state)

    assert game.vampire("B1").blood == 0
