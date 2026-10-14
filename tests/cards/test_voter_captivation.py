"""Voter Captivation (krcg id 102131, `src/vtesbot/cards/voter_captivation.py`).

Card text: "Only usable after resolution of a political action whose
referendum passed. [pre] This vampire gains 1 blood for each vote by which
the referendum passed. [PRE] As above, but move up to 2 of those blood to
your pool instead of this vampire." Rulings: "Is played after resolution,
after all combats (if any) are handled, but still during the action. Action
modifiers and effects that can be played 'after resolution' can be played
before or after it." [PIB 20150915] [LSJ 19981028] [ANK 20190425]; "Is played
after the referendum is resolved. If the effect of the referendum ousts the
acting Methuselah, there is no time to play it to prevent the ousting." [RTR
19951110]; "Can be used after a referendum that is automatically passing, but
the vote is considered to have passed by 0 votes." [LSJ 19980107]
[PIB 20150105].

One assertion per clause/qualifier/ruling: card-in-hand and discipline
gating for each clause; "ready" eligibility (torpor excluded); the basic
clause's blood gain (capped at capacity, per `add_blood`/OQ-8); the superior
clause's redirect-to-pool choice (bounded at `min(2, margin)`, including the
`margin < 2` edge case and the no-decision-needed `margin == 0` edge case);
either Methuselah (not only the referendum's caller) may be offered the play
for their own eligible vampire; and an end-to-end pass through a real
political action (Kine Resources Contested) and `minion_phase`. The "played
after resolution ... before or after [another such effect]" ruling is a
structural property of `hooks.resolve_impulse_window`'s own repeat-until-
both-pass loop (already proven generically by `tests/rules/
test_referendum_resolved.py`), not independently re-tested at the card level;
the "ousts the acting Methuselah" and "automatically passing, by 0 votes"
rulings describe timing/engine states this pool cannot yet produce (no
automatically-passing mechanism exists, `docs/OPEN_QUESTIONS.md` OQ-6) --
the 0-votes edge case is still covered below directly against the provider.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.kine_resources_contested import KRCG_ID as KINE_KRCG_ID
from vtesbot.cards.registry import Status, get
from vtesbot.cards.voter_captivation import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import REFERENDUM_RESOLVED_HOOK
from vtesbot.engine.phases.minion import minion_phase

NAME = "Voter Captivation"


def _vc_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="Action Modifier")


def _offer(state, player, margin, **extra):
    return hooks.offer(
        REFERENDUM_RESOLVED_HOOK,
        state,
        player=player,
        caller=extra.pop("caller", player),
        other=extra.pop("other", "P2" if player == "P1" else "P1"),
        caller_vampire_id=extra.pop("caller_vampire_id", None),
        margin=margin,
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


def test_basic_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0, disciplines=("pre",))
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game.state, "P1", margin=2)

    assert options == []


def test_basic_not_offered_without_pre():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0, disciplines=())
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game.state, "P1", margin=2)

    assert options == []


def test_basic_not_offered_for_a_torpid_vampire():
    """`torpid_vampire` has no `disciplines=` parameter -- build a ready
    [pre] vampire, then flip `.zone` directly (the only field this test
    needs to vary) to isolate the "ready" gate specifically."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=0, disciplines=("pre",)
    )
    p1.vampires[-1].zone = "torpor"
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game.state, "P1", margin=2)

    assert options == []


def test_superior_not_offered_with_only_basic_pre():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=0, disciplines=("pre",)
    )
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()

    basic = _offer(game.state, "P1", margin=2)
    assert {o.choice.value for o in basic} == {"voter_captivation:basic:V1"}


def test_superior_offered_with_superior_pre():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=0, disciplines=("PRE",)
    )
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game.state, "P1", margin=2)

    values = {o.choice.value for o in options}
    # Superior Presence unlocks either effect (Rulebook SS3) -- both offered.
    assert values == {"voter_captivation:basic:V1", "voter_captivation:superior:V1"}


def test_offered_to_either_player_independent_of_who_called_the_referendum():
    """The hook fires at both `caller` and `other`; P2 (not the caller)
    controls the only eligible vampire here, so only P2 sees an option."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=5, blood=0, disciplines=("pre",)
    )
    p2.hand.append(_vc_card())
    game = builder.build()

    p1_options = _offer(game.state, "P1", margin=2, caller="P1", other="P2")
    p2_options = _offer(game.state, "P2", margin=2, caller="P1", other="P2")

    assert p1_options == []
    assert {o.choice.value for o in p2_options} == {"voter_captivation:basic:B1"}


# --- "[pre] This vampire gains 1 blood for each vote by which the referendum
# passed." ---------------------------------------------------------------


def test_basic_gains_margin_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=0, disciplines=("pre",)
    )
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game.state, "P1", margin=3)
    option = next(o for o in options if o.choice.value == "voter_captivation:basic:V1")
    option.apply(game.state)

    assert game.blood_of("V1") == 3
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


def test_basic_blood_gain_is_capped_at_effective_capacity():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=2, blood=1, disciplines=("pre",)
    )
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game.state, "P1", margin=5)
    option = next(o for o in options if o.choice.value == "voter_captivation:basic:V1")
    option.apply(game.state)

    assert game.blood_of("V1") == 2  # capped, not 1 + 5


# --- "[PRE] As above, but move up to 2 of those blood to your pool instead
# of this vampire." -------------------------------------------------------


def test_superior_redirect_choices_bounded_by_min_two_and_margin():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=0, disciplines=("PRE",)
    )
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game.state, "P1", margin=1)  # margin < 2: only 0 or 1 legal
    option = next(o for o in options if o.choice.value == "voter_captivation:superior:V1")
    actor = ScriptedAgent("P1")
    actor.expect("voter_captivation_redirect", "redirect:1")
    game.state.agents["P1"] = actor

    option.apply(game.state)

    assert game.blood_of("V1") == 0
    assert game.pool_of("P1") == 31
    actor.assert_exhausted()


def test_superior_moves_up_to_two_blood_to_pool_instead_of_the_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=0, disciplines=("PRE",)
    )
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game.state, "P1", margin=4)
    option = next(o for o in options if o.choice.value == "voter_captivation:superior:V1")
    actor = ScriptedAgent("P1")
    actor.expect("voter_captivation_redirect", "redirect:2")
    game.state.agents["P1"] = actor

    option.apply(game.state)

    assert game.blood_of("V1") == 2  # 4 margin - 2 redirected
    assert game.pool_of("P1") == 32  # 30 + 2 redirected
    actor.assert_exhausted()


def test_superior_redirect_decision_offers_zero_as_a_legal_choice():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=0, disciplines=("PRE",)
    )
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game.state, "P1", margin=3)
    option = next(o for o in options if o.choice.value == "voter_captivation:superior:V1")
    actor = ScriptedAgent("P1")
    actor.expect("voter_captivation_redirect", "redirect:0")
    game.state.agents["P1"] = actor

    option.apply(game.state)

    assert game.blood_of("V1") == 3  # behaves exactly like the basic clause
    assert game.pool_of("P1") == 30
    actor.assert_exhausted()


def test_superior_margin_zero_binds_directly_with_no_decision_raised():
    """ "Can be used after a referendum that is automatically passing, but
    the vote is considered to have passed by 0 votes" -- not reachable
    through a real referendum today (no automatically-passing mechanism
    exists), but the provider itself must not crash or raise a vacuous
    `Decision` if it is ever reached this way."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=0, disciplines=("PRE",)
    )
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game.state, "P1", margin=0)
    option = next(o for o in options if o.choice.value == "voter_captivation:superior:V1")
    actor = ScriptedAgent("P1")  # no scripted answers: must not be asked anything
    game.state.agents["P1"] = actor

    option.apply(game.state)

    assert game.blood_of("V1") == 0
    assert game.pool_of("P1") == 30
    actor.assert_exhausted()


# --- per-vampire once-per-action cap (Rulebook SS2: "A minion cannot play
# the same action modifier card more than once during a single action") ----


def test_second_copy_cannot_regrant_the_same_vampire_within_one_window():
    """`rules-auditor` finding: two copies of this card in hand previously
    let the same target vampire be fed (and apply) the basic clause's
    option twice in the same `REFERENDUM_RESOLVED_HOOK` window."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=0, disciplines=("pre",)
    )
    p1.hand.append(_vc_card())
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()
    pending: dict = {}

    first = _offer(game.state, "P1", margin=3, pending=pending)
    option = next(o for o in first if o.choice.value == "voter_captivation:basic:V1")
    option.apply(game.state)

    assert game.blood_of("V1") == 3

    second = _offer(game.state, "P1", margin=3, pending=pending)

    assert second == []  # V1 already granted this window; the second copy has no target.


def test_second_copy_may_still_benefit_a_different_vampire_within_one_window():
    """The once-per-action cap is per *minion* (target vampire), not
    global: a second copy may still grant a second, different ready
    vampire of the same controller within the same window."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=0, disciplines=("pre",))
    p1.ready_vampire("V2", capacity=5, blood=0, disciplines=("pre",))
    p1.hand.append(_vc_card())
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()
    pending: dict = {}

    first = _offer(game.state, "P1", margin=2, pending=pending)
    next(o for o in first if o.choice.value == "voter_captivation:basic:V1").apply(game.state)

    second = _offer(game.state, "P1", margin=2, pending=pending)
    assert {o.choice.value for o in second} == {"voter_captivation:basic:V2"}
    next(o for o in second if o.choice.value == "voter_captivation:basic:V2").apply(game.state)

    assert game.blood_of("V1") == 2
    assert game.blood_of("V2") == 2


# --- end-to-end through a real political action and minion_phase -----------


def test_end_to_end_through_a_real_passing_political_action():
    """Kine Resources Contested's referendum passes 1-0 (P1's own
    political-action-card vote, uncontested); Voter Captivation then fires
    in the `REFERENDUM_RESOLVED_HOOK` window with `margin == 1`."""
    builder = ScenarioBuilder(seed=1)
    # `blood=1` (not 0): a blood-0 ready vampire triggers the mandatory
    # "must hunt" rule (`engine/phases/minion.py::minion_phase`), which
    # would consume V1's turn before the scripted optional-action choices
    # below are ever offered.
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("pre",)
    )
    p1.hand.append(
        LibraryCard(
            krcg_id=KINE_KRCG_ID, name="Kine Resources Contested", card_type="Political Action"
        )
    )
    p1.hand.append(_vc_card())
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("kine_resources_contested_allocation", "allocate:2")
    actor.expect("referendum_resolved", "voter_captivation:basic:V1")
    # No further decision follows: the card is now gone from hand, so the
    # next `resolve_impulse_window` offer is empty for both sides and the
    # window closes silently (no vacuous "pass" `Decision` is ever raised).
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.blood_of("V1") == 2  # 1 (starting) + margin 1 (1 vote for, 0 against)
    assert game.pool_of("P1") == 28  # 30 - 2 (self-allocated share)
    actor.assert_exhausted()
