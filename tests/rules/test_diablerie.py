"""Diablerie resolution (`engine/diablerie.py::resolve_diablerie`) + the
triggering "Diablerise a Vampire in Torpor" default minion action
(`engine/phases/minion.py::ACTION_DIABLERIE`/`_perform_diablerise`).
Rulebook §4 Minion Phase (lines 380-404) and §4 Torpor > "Diablerie"/"The
Blood Hunt" (lines 1076-1118), `data/sources/rulebook/2026-10-09/
4-detailed-turn-sequence.md`.

Per the `rules-scenario-test` skill: the triggering-action tests
(`minion_phase`, below) exercise the generic engine mechanism end to end;
the resolution-mechanism tests call `resolve_diablerie` directly (mirrors
`tests/rules/test_politics.py`'s own direct `resolve_referendum` calls) --
no real card (Queen Anne) is used anywhere here, only a synthetic fake
`DIABLERIE_HOOK` provider standing in for her eventual "she can unlock"
clause.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.decision import Choice
from vtesbot.engine.diablerie import DIABLERIE_HOOK, resolve_diablerie
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import minion_phase
from vtesbot.engine.politics import resolve_referendum

# --- The triggering action (`minion_phase`) ---------------------------------


def test_diablerise_not_offered_without_any_torpid_target():
    """ "Never offer a play that cannot resolve" (`cards/line_brawl.py`
    precedent): with no vampire in torpor anywhere, "diablerise" never
    appears among `action_choice`'s offered choices, so bleed is chosen
    instead without the agent ever seeing a diablerise option."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:D")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    actor.assert_exhausted()


def test_undirected_diablerie_of_own_torpid_vampire_evades_a_bare_block():
    """ "Undirected action, ... +1 stealth, if the acting vampire and the
    vampire in torpor have the same controller." Mirrors `test_minion_hunt.
    py`'s own "always evades a block attempt due to its baseline stealth"
    shape (+1 stealth always beats a bare 0-intercept blocker, but the
    block attempt is still offered and re-offered once before being
    declined). Diablerie step 1's overflow drain is exercised here too: the
    victim (4 blood) overflows the diablerist's remaining capacity (5 - 2 =
    3), so only 3 of the 4 blood actually arrive. With no titles/cards/Edge
    anywhere, the automatic Blood Hunt referendum ties 0-0 and fails
    ("[t]ied referendums fail"): the diablerist survives."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=2).torpid_vampire(
        "V", capacity=4, blood=4
    )
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:D")
    actor.expect("action_choice", "diablerise")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.blood_of("D") == 5  # 2 + min(4, 5-2) = 5, 1 blood drained off
    assert game.zone_of("V") == "burned"
    assert game.zone_of("D") == "ready"  # Blood Hunt tied 0-0 and failed
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_directed_diablerie_of_the_opponents_torpid_vampire_is_blockable_at_bare_stealth():
    """ "Directed action, ... 0 stealth, if ... different controllers." A
    bare blocker's 0 baseline intercept succeeds against 0 stealth
    (intercept >= stealth), same shape as `test_minion_bleed.py`'s own
    "successful block locks blocker and prevents [the action] from
    resolving" test: diablerie never resolves, the victim stays in
    torpor."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=2)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1).torpid_vampire(
        "V", capacity=4, blood=4
    )
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:D")
    actor.expect("action_choice", "diablerise")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.zone_of("V") == "torpor"  # diablerie never resolved
    assert game.blood_of("V") == 4
    assert game.blood_of("D") == 2
    assert game.vampire("B1").locked is True  # a successful block locks the blocker
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_multiple_torpid_targets_raise_an_explicit_target_decision():
    """With more than one legal torpid target (one on each side), the
    target is bound at announce time via its own `"diablerise_target"`
    `Decision` -- same "all terms fixed now" shape as `cards/line_brawl.py`'s
    `[pot]` clause target choice -- not deferred or guessed."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=2).torpid_vampire(
        "V1", capacity=3, blood=1
    )
    builder.player("P2", pool=30).torpid_vampire("V2", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:D")
    actor.expect("action_choice", "diablerise")
    actor.expect("diablerise_target", "diablerise_target:V2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")  # no ready vampire: no block decision raised

    minion_phase(game.state, "P1")

    assert game.zone_of("V2") == "burned"  # chosen target: diablerised
    assert game.zone_of("V1") == "torpor"  # not chosen: untouched
    actor.assert_exhausted()


# --- Resolution mechanism (`resolve_diablerie`, called directly) ------------


def test_equipment_may_be_taken_by_the_diablerist():
    """Step 2: "The diablerist may take any equipment on the victim" -- a
    per-item `Decision` (CLAUDE.md rule 3), not an all-or-nothing grant.
    Taking it re-hosts the attachment onto the diablerist and reassigns its
    controller."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=0)
    builder.player("P2", pool=30).torpid_vampire("V", capacity=3, blood=0)
    game = builder.build()
    victim = game.vampire("V")
    attachment = CardAttachment(
        krcg_id=999, name="Fake Equipment", controller="P2", is_equipment=True
    )
    victim.attachments.append(attachment)
    actor = ScriptedAgent("P1").expect("diablerie_take_equipment", "take")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    resolve_diablerie(game.state, "P1", game.vampire("D"), "P2", victim)

    assert attachment not in victim.attachments
    assert attachment in game.vampire("D").attachments
    assert attachment.controller == "P1"
    assert attachment.zone == "attached"  # taken, not burned
    actor.assert_exhausted()


def test_declined_equipment_burns_with_the_victim():
    """Step 2/3: declining leaves the equipment on the victim, which is
    then burned along with her ("Any cards and counters on them are also
    burned")."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=0)
    builder.player("P2", pool=30).torpid_vampire("V", capacity=3, blood=0)
    game = builder.build()
    victim = game.vampire("V")
    attachment = CardAttachment(
        krcg_id=999, name="Fake Equipment", controller="P2", is_equipment=True
    )
    victim.attachments.append(attachment)
    actor = ScriptedAgent("P1").expect("diablerie_take_equipment", "leave")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    resolve_diablerie(game.state, "P1", game.vampire("D"), "P2", victim)

    assert attachment in victim.attachments  # never moved
    assert attachment.zone == "burned"
    assert attachment.controller == "P2"  # unchanged
    actor.assert_exhausted()


def test_non_equipment_attachment_is_never_offered_and_burns_automatically():
    """A discipline/archetype master-card attachment (e.g. Celerity) or a
    Unique master card (e.g. Fame) is not equipment (`CardAttachment.
    is_equipment` defaults `False`) and is never offered the take/leave
    choice at all -- it simply burns with the victim, step 3. No scripted
    answer is provided for either agent: any unscripted decision would
    fail the test loudly."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=0)
    builder.player("P2", pool=30).torpid_vampire("V", capacity=3, blood=0)
    game = builder.build()
    victim = game.vampire("V")
    attachment = CardAttachment(krcg_id=998, name="Fake Celerity", controller="P2")
    victim.attachments.append(attachment)
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    resolve_diablerie(game.state, "P1", game.vampire("D"), "P2", victim)

    assert attachment in victim.attachments
    assert attachment.zone == "burned"


def test_blood_hunt_referendum_passes_and_burns_the_diablerist():
    """The Blood Hunt: "If the referendum passes, a blood hunt is called,
    and the diablerist is burned." The victim's controller's own titled
    vampire (2 votes, a ready prince) casts "for", outvoting the
    diablerist's side (which has no vote source at all here), 2-0."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=0)
    builder.player("P2", pool=30).torpid_vampire("V", capacity=3, blood=0).ready_vampire(
        "Judge", capacity=3, blood=1, title="Prince"
    )
    game = builder.build()
    victim = game.vampire("V")
    actor = ScriptedAgent("P1")
    defender = ScriptedAgent("P2").expect("polling_step_cast", "for:title:Judge")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    resolve_diablerie(game.state, "P1", game.vampire("D"), "P2", victim)

    assert game.zone_of("D") == "burned"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_blood_hunt_referendum_ties_and_the_diablerist_survives():
    """ "Tied referendums fail." With no vote source at all on either
    side, the referendum ties 0-0, and the diablerist is not burned by it
    -- proving the automatic referendum genuinely ran (as opposed to being
    skipped), even though it had no effect here."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=0)
    builder.player("P2", pool=30).torpid_vampire("V", capacity=3, blood=0)
    game = builder.build()
    victim = game.vampire("V")
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    resolve_diablerie(game.state, "P1", game.vampire("D"), "P2", victim)

    assert game.zone_of("D") == "ready"


def test_the_undirected_case_does_not_collapse_both_referendum_sides_onto_one_player():
    """Regression test for a real bug caught while building this module:
    diablerizing one's *own* torpid vampire makes `victim_player ==
    diablerist_player`, which must never be used as the Blood Hunt
    referendum's `other_player` (it would collapse the whole two-sided
    mechanism onto a single Methuselah). The actual opponent (`P2`, who
    controls neither the diablerist nor the victim here) must still be
    the one offered the referendum's vote source."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=0).torpid_vampire(
        "V", capacity=3, blood=0
    )
    builder.player("P2", pool=30).ready_vampire("Judge", capacity=3, blood=1, title="Prince")
    game = builder.build()
    victim = game.vampire("V")
    actor = ScriptedAgent("P1")
    defender = ScriptedAgent("P2").expect("polling_step_cast", "against:title:Judge")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    resolve_diablerie(game.state, "P1", game.vampire("D"), "P1", victim)

    assert game.zone_of("D") == "ready"  # 2 against vs 0 for: fails, diablerist survives
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_the_automatic_blood_hunt_never_grants_the_caller_a_free_political_action_card_vote():
    """`engine/politics.py::resolve_referendum`'s `include_caller_card_vote
    =False` fix: without it, `_collect_vote_sources` would unconditionally
    hand the diablerist's side a "+1 vote for casting a political action
    card" source even though nobody cast one to trigger this automatic
    referendum. Proven here with the diablerist's own controller (P1)
    holding a "Political Action"-type card in hand: `political_action_card:
    P1` must never be offered, but -- the fix's symmetric half -- P1 may
    still burn that same card from hand for a vote exactly like P2 could
    (Rulebook §4 Politics > Gaining Votes > Political Action Cards: "Each
    Methuselah may gain 1 vote by using a political action card", not a
    caller-only right when nobody has claimed it by casting)."""

    class AssertingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "polling_step_cast":
                offered = {c.value for c in decision.choices}
                assert not any("political_action_card:P1" == v for v in offered), offered
            return super().decide(observation, decision)

    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=0).hand_cards(
        ["Fake PAC"], card_type="Political Action"
    )
    builder.player("P2", pool=30).torpid_vampire("V", capacity=3, blood=0)
    game = builder.build()
    victim = game.vampire("V")
    actor = AssertingAgent("P1").expect("polling_step_cast", "for:political_action_card_hand:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    resolve_diablerie(game.state, "P1", game.vampire("D"), "P2", victim)

    assert game.zone_of("D") == "burned"  # 1-0 for: P1's own burned-from-hand vote passes it
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Fake PAC"]
    actor.assert_exhausted()


def test_diablerie_hook_fires_while_the_diablerist_is_still_in_play_before_the_blood_hunt():
    """Generic reaction-hook proof (no real card): a fake `DIABLERIE_HOOK`
    provider, standing in for Queen Anne's eventual "After she diablerizes
    a vampire, she can unlock" clause, is offered an *optional* choice
    right after diablerie resolves -- and, crucially, before the automatic
    Blood Hunt referendum below it, which could otherwise burn the
    diablerist first. The fake provider records the diablerist's `zone` at
    the moment it fires and actually unlocks her; a passing Blood Hunt
    afterward still burns her -- the unlock was real, just moot."""
    seen_zone_at_hook_time: list[str] = []

    def fake_queen_anne_unlock(state, context):
        diablerist = state.players[context["player"]].vampires.get(context["diablerist"])
        if diablerist is None or not diablerist.locked:
            return []  # already unlocked (or not this player's own diablerist): nothing to offer
        seen_zone_at_hook_time.append(diablerist.zone)

        def _apply(s):
            diablerist.locked = False

        return [HookOption(choice=Choice("fake_unlock", "Unlock the diablerist"), apply=_apply)]

    hooks.register(DIABLERIE_HOOK, fake_queen_anne_unlock)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=0, locked=True)
    builder.player("P2", pool=30).torpid_vampire("V", capacity=3, blood=0).ready_vampire(
        "Judge", capacity=3, blood=1, title="Prince"
    )
    game = builder.build()
    victim = game.vampire("V")
    actor = ScriptedAgent("P1").expect(DIABLERIE_HOOK, "fake_unlock")
    # P2 is never asked a `DIABLERIE_HOOK` decision at all: the fake
    # provider only ever answers for the diablerist's own controller
    # (D is not among P2's own vampires), and once used it stops offering
    # anything further for P1 either (the `not diablerist.locked` guard).
    defender = ScriptedAgent("P2").expect("polling_step_cast", "for:title:Judge")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    resolve_diablerie(game.state, "P1", game.vampire("D"), "P2", victim)

    assert seen_zone_at_hook_time == ["ready"]  # not "burned": fired before the Blood Hunt
    assert game.vampire("D").locked is False  # the optional unlock was actually applied
    assert game.zone_of("D") == "burned"  # the Blood Hunt still passed afterward, 2-0
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_diablerie_hook_with_no_provider_registered_is_a_safe_no_op():
    """Zero-regression check: with nothing registered against
    `DIABLERIE_HOOK`, `resolve_impulse_window` raises no decision at all
    and resolution proceeds straight to the Blood Hunt."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D", capacity=5, blood=0)
    builder.player("P2", pool=30).torpid_vampire("V", capacity=3, blood=0)
    game = builder.build()
    victim = game.vampire("V")
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    resolve_diablerie(game.state, "P1", game.vampire("D"), "P2", victim)

    assert game.zone_of("V") == "burned"
    assert game.zone_of("D") == "ready"


def test_resolve_referendum_include_caller_card_vote_false_offers_symmetric_from_hand_burn():
    """Unit-level proof of the `engine/politics.py::resolve_referendum`
    parameter itself (independent of diablerie): with
    `include_caller_card_vote=False` and *both* players holding a
    "Political Action"-type card in hand, both -- not just `other_player`
    -- are offered the "burn a political action card from hand" source,
    and neither is offered the "cast" source (nobody cast anything)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1).hand_cards(
        ["Fake PAC 1"], card_type="Political Action"
    )
    builder.player("P2", pool=30).hand_cards(["Fake PAC 2"], card_type="Political Action")
    game = builder.build()
    actor = ScriptedAgent("P1").expect("polling_step_cast", "for:political_action_card_hand:P1")
    defender = ScriptedAgent("P2").expect(
        "polling_step_cast", "against:political_action_card_hand:P2"
    )
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    votes_for, votes_against, casts = resolve_referendum(
        game.state, "P1", "P2", game.vampire("V1"), include_caller_card_vote=False
    )

    assert votes_for == 1 and votes_against == 1
    assert {source_id for (_player, source_id, _votes, _direction) in casts} == {
        "political_action_card_hand:P1",
        "political_action_card_hand:P2",
    }
    actor.assert_exhausted()
    defender.assert_exhausted()
