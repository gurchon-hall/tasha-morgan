"""Queen Anne (krcg id 201647, `src/vtesbot/cards/queen_anne.py`).

Card text: "Camarilla Prince of London: During the polling step of a
referendum called by Anne, she can burn 1 blood to force a younger
Camarilla vampire to abstain. After she diablerizes a vampire, she can
unlock. +1 bleed." No ruling on file.

One assertion per clause/judgment call (module docstring for the full
reasoning): clause 1's "forces abstain" end to end, the capacity-tie
exclusion (same capacity is neither older nor younger), the "called by
Anne" gate, eligibility on either Methuselah's side, the non-Camarilla
exclusion, the torpid-target exclusion, the no-vote-source (untitled
target) exclusion, the `is_ready_unlocked` gate on Anne herself, the
blood-cost gate, the `before_cast`-only timing, and the once-per-
referendum cap; clause 2's unlock end to end through a real
`resolve_diablerie` call (including the subsequent Blood Hunt), the
"Anne herself must be the diablerist" scoping, and the already-unlocked
no-op guard; clause 3's +1 bleed (and its absence for a different
vampire's bleed).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.queen_anne import KRCG_ID
from vtesbot.engine import CryptCard, Sect, hooks
from vtesbot.engine.diablerie import DIABLERIE_HOOK, resolve_diablerie
from vtesbot.engine.phases.minion import minion_phase
from vtesbot.engine.politics import POLLING_STEP_HOOK, resolve_referendum

NAME = "Queen Anne"
DISCIPLINES = ("aus", "obf", "DOM", "FOR", "PRE")


def _make_anne(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Queen Anne's real printed
    identity (`CryptCard` is frozen, mirrors `test_diana_iadanza.py::
    _make_diana`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=10,
        group=6,
        clan="Ventrue",
        title="Prince",
        disciplines=DISCIPLINES,
        sect=Sect.CAMARILLA,
    )


def _set_card_fields(builder_player, instance_id: str, *, sect=None, title=None) -> None:
    """Overwrite `sect` and/or `title` on an already-built vampire's
    (frozen) `card`, keeping every other printed field. `ready_vampire`
    already accepts a `title` kwarg directly, but has no `sect` kwarg
    (mirrors `test_lucinde_alastor.py::_set_sect`); also used for
    `torpid_vampire`, whose builder method supports neither."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    old = vampire.card
    vampire.card = CryptCard(
        krcg_id=old.krcg_id,
        name=old.name,
        capacity=old.capacity,
        group=old.group,
        clan=old.clan,
        title=title if title is not None else old.title,
        disciplines=old.disciplines,
        sect=sect if sect is not None else old.sect,
    )


def _pending():
    return {"extra_sources": [], "forced_abstain": set()}


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Queen Anne"
    assert reg.blocked_reason is None


# --- "During the polling step of a referendum called by Anne, she can -----
# --- burn 1 blood to force a younger Camarilla vampire to abstain." -------


def test_forces_a_younger_camarilla_vampire_to_abstain_end_to_end():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    _set_card_fields(p2, "B1", sect=Sect.CAMARILLA)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect(POLLING_STEP_HOOK, "queen_anne_forced_abstain:B1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Anne1")
    defender = ScriptedAgent("P2")  # B1's vote source is forced to abstain: no decision at all.
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    votes_for, votes_against, casts = resolve_referendum(
        game.state, "P1", "P2", game.vampire("Anne1")
    )

    assert all(source_id != "title:B1" for (_player, source_id, _votes, _direction) in casts)
    assert votes_for == 3 and votes_against == 0  # 1 (pac) + 2 (Anne's own Prince title)
    assert game.blood_of("Anne1") == 0  # 1 blood burned
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_not_offered_for_a_vampire_with_the_same_capacity_as_anne():
    """ "A vampire with a larger capacity than another is said to be
    older, and one with a smaller capacity is younger" -- same capacity
    is neither, so it does not qualify."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=10, blood=1, title="Primogen")
    _set_card_fields(p2, "B1", sect=Sect.CAMARILLA)
    game = builder.build()

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id=game.vampire("Anne1").instance_id,
        pending=_pending(),
    )

    assert all(not o.choice.value.startswith("queen_anne_forced_abstain") for o in options)


def test_not_offered_when_the_referendum_was_not_called_by_anne_herself():
    """ "a referendum called by **Anne**" -- not any referendum her
    controller happens to call, even with another titled vampire of
    their own."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1)
    _make_anne(p1, "Anne1")
    p1.ready_vampire("OtherCaller", capacity=4, blood=1, title="Primogen")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    _set_card_fields(p2, "B1", sect=Sect.CAMARILLA)
    game = builder.build()

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id=game.vampire("OtherCaller").instance_id,
        pending=_pending(),
    )

    assert all(not o.choice.value.startswith("queen_anne_forced_abstain") for o in options)


def test_offered_for_a_qualifying_vampire_on_either_side():
    """ "a younger Camarilla vampire" carries no "yours"/"opponent's"
    qualifier -- both Methuselahs' qualifying vampires are offered as
    targets."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1)
    _make_anne(p1, "Anne1")
    p1.ready_vampire("Own1", capacity=3, blood=1, title="Primogen")
    _set_card_fields(p1, "Own1", sect=Sect.CAMARILLA)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    _set_card_fields(p2, "B1", sect=Sect.CAMARILLA)
    game = builder.build()

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id=game.vampire("Anne1").instance_id,
        pending=_pending(),
    )

    offered = {o.choice.value for o in options}
    assert "queen_anne_forced_abstain:Own1" in offered
    assert "queen_anne_forced_abstain:B1" in offered


def test_not_offered_for_a_non_camarilla_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    _set_card_fields(p2, "B1", sect=Sect.ANARCH)
    game = builder.build()

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id=game.vampire("Anne1").instance_id,
        pending=_pending(),
    )

    assert all(not o.choice.value.startswith("queen_anne_forced_abstain") for o in options)


def test_not_offered_for_a_torpid_vampire():
    """A torpid vampire already must abstain (Rulebook §4: "A vampire in
    torpor cannot cast any votes or ballots"); forcing one would be a
    no-op, so it is never offered."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.torpid_vampire("B1", capacity=3, blood=1)
    _set_card_fields(p2, "B1", sect=Sect.CAMARILLA, title="Primogen")
    game = builder.build()

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id=game.vampire("Anne1").instance_id,
        pending=_pending(),
    )

    assert all(not o.choice.value.startswith("queen_anne_forced_abstain") for o in options)


def test_not_offered_for_a_camarilla_vampire_with_no_title():
    """A Camarilla vampire with no title has no vote source to force into
    abstention either -- offering it would be equally inert."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1)
    _set_card_fields(p2, "B1", sect=Sect.CAMARILLA)
    game = builder.build()

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id=game.vampire("Anne1").instance_id,
        pending=_pending(),
    )

    assert all(not o.choice.value.startswith("queen_anne_forced_abstain") for o in options)


def test_not_offered_if_anne_is_locked():
    """No on-file ruling grants a "usable while locked" exception (unlike
    Alexa Draper), so the ordinary `is_ready_unlocked` default applies."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1, locked=True)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    _set_card_fields(p2, "B1", sect=Sect.CAMARILLA)
    game = builder.build()

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id=game.vampire("Anne1").instance_id,
        pending=_pending(),
    )

    assert all(not o.choice.value.startswith("queen_anne_forced_abstain") for o in options)


def test_not_offered_if_anne_has_no_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=0)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    _set_card_fields(p2, "B1", sect=Sect.CAMARILLA)
    game = builder.build()

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id=game.vampire("Anne1").instance_id,
        pending=_pending(),
    )

    assert all(not o.choice.value.startswith("queen_anne_forced_abstain") for o in options)


def test_not_offered_during_the_mid_cast_window():
    """`pending["forced_abstain"]` is consumed once, right after the
    pre-cast window closes -- adding to it mid-cast would be a silent
    no-op, so this is never offered at `phase == "mid_cast"`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    _set_card_fields(p2, "B1", sect=Sect.CAMARILLA)
    game = builder.build()

    options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="mid_cast",
        caller="P1",
        caller_vampire_id=game.vampire("Anne1").instance_id,
        pending=_pending(),
    )

    assert all(not o.choice.value.startswith("queen_anne_forced_abstain") for o in options)


def test_only_usable_once_per_referendum():
    """Rulebook §3 "Wording templates" > "During X, do Y", verbatim:
    "only one Y can be done per X with this card" -- a second qualifying
    target in the same referendum cannot also be forced to abstain."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=5)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, title="Primogen")
    _set_card_fields(p2, "B1", sect=Sect.CAMARILLA)
    p2.ready_vampire("B2", capacity=3, blood=1, title="Bishop")
    _set_card_fields(p2, "B2", sect=Sect.CAMARILLA)
    game = builder.build()
    anne_id = game.vampire("Anne1").instance_id
    pending = _pending()

    first_options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id=anne_id,
        pending=pending,
    )
    assert {o.choice.value for o in first_options} == {
        "queen_anne_forced_abstain:B1",
        "queen_anne_forced_abstain:B2",
    }
    by_value = {o.choice.value: o for o in first_options}
    by_value["queen_anne_forced_abstain:B1"].apply(game.state)

    second_options = hooks.offer(
        POLLING_STEP_HOOK,
        game.state,
        player="P1",
        phase="before_cast",
        caller="P1",
        caller_vampire_id=anne_id,
        pending=pending,
    )

    assert second_options == []
    assert pending["forced_abstain"] == {f"title:{game.vampire('B1').instance_id}"}
    assert game.blood_of("Anne1") == 4  # exactly one burn, not two


# --- "After she diablerizes a vampire, she can unlock." -------------------


def test_anne_unlocks_after_diablerizing_a_vampire_end_to_end():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=0, locked=True)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.torpid_vampire("V", capacity=3, blood=0)
    game = builder.build()
    victim = game.vampire("V")
    actor = ScriptedAgent("P1")
    actor.expect(DIABLERIE_HOOK, "queen_anne_diablerie_unlock")
    # Anne herself is a ready, titled (Prince) vampire, so her own "title:"
    # vote source is offered in the automatic Blood Hunt too; declining it
    # (rather than casting it for herself) keeps the referendum at 0-0 so it
    # ties and fails, isolating this test to clause 2 alone.
    actor.expect("polling_step_cast", "pass")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    resolve_diablerie(game.state, "P1", game.vampire("Anne1"), "P2", victim)

    assert game.vampire("Anne1").locked is False  # the optional unlock was actually applied
    assert game.zone_of("Anne1") == "ready"  # Blood Hunt ties 0-0 (declined) and fails
    assert game.zone_of("V") == "burned"
    actor.assert_exhausted()


def test_not_offered_if_anne_is_not_the_diablerist():
    """Scoped to Anne herself being the diablerist, not merely present in
    play (another vampire controlled by the same Methuselah diablerises
    instead)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("D", capacity=5, blood=0, locked=True)
    p1.ready_vampire("Anne1", capacity=10, blood=0, locked=True)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.torpid_vampire("V", capacity=3, blood=0)
    game = builder.build()
    victim = game.vampire("V")
    actor = ScriptedAgent("P1")  # no DIABLERIE_HOOK decision raised at all
    # Anne is a ready, titled (Prince) vampire on P1's own side, so the
    # Blood Hunt still offers her "title:" vote source; decline it (same
    # reasoning as the sibling "unlocks end to end" test).
    actor.expect("polling_step_cast", "pass")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    resolve_diablerie(game.state, "P1", game.vampire("D"), "P2", victim)

    assert game.vampire("Anne1").locked is True  # untouched: she was not the diablerist
    assert game.zone_of("D") == "ready"
    actor.assert_exhausted()


def test_not_offered_if_anne_is_already_unlocked():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=0, locked=False)
    _make_anne(p1, "Anne1")
    p2 = builder.player("P2", pool=30)
    p2.torpid_vampire("V", capacity=3, blood=0)
    game = builder.build()
    victim = game.vampire("V")
    actor = ScriptedAgent("P1")  # no DIABLERIE_HOOK decision: already unlocked
    actor.expect("polling_step_cast", "pass")  # decline Anne's own "title:" Blood Hunt vote
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    resolve_diablerie(game.state, "P1", game.vampire("Anne1"), "P2", victim)

    assert game.vampire("Anne1").locked is False
    assert game.zone_of("Anne1") == "ready"
    actor.assert_exhausted()


# --- "+1 bleed" -------------------------------------------------------------


def test_plus_1_bleed_when_anne_herself_bleeds():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1)
    _make_anne(p1, "Anne1")
    builder.player("P2", pool=30).ready_vampire("D", capacity=3, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:Anne1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base bleed 1 + Anne's own +1
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_no_bleed_bonus_when_a_different_vampire_bleeds():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Anne1", capacity=10, blood=1, locked=True)  # already acted this turn
    _make_anne(p1, "Anne1")
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

    assert game.pool_of("P2") == 29  # base bleed 1 only, Anne did not act
    actor.assert_exhausted()
    defender.assert_exhausted()
