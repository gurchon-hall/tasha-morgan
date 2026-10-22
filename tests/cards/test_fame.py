"""Fame (krcg id 100698, `src/vtesbot/cards/fame.py`).

Card text: "Unique.\nPut this card on a ready vampire. After this vampire
goes to torpor, their controller burns 3 pool. During each Methuselah's
unlock phase, if this vampire is in torpor, that Methuselah burns 1 pool."

One ruling on file: "Paying a pool during the unlock phase can be ordered
with other unlock effects by the acting Methuselah, but must be handled
before another Methuselah has the opportunity to use an unlock effect."
[LSJ 20110121] -- exercised below by proving the mandatory unlock-phase
pool burn resolves correctly alongside another, genuinely optional,
unlock-phase effect (the Edge gain) in the very same `unlock_phase` call.

One assertion per clause/behaviour: "Unique" (a contest between two
independently-played copies, built entirely on the generic ENG-014
Contested-Cards machinery with no Fame-specific contest code), "a ready
vampire" (either player's, strictly `zone == "ready"` -- a torpid vampire
is excluded, unlike Celerity's own looser targeting), "their controller
burns 3 pool" (the host vampire's own controller, which may differ from
Fame's own controller), and "that Methuselah burns 1 pool" during *each*
Methuselah's own unlock phase while the host vampire stays in torpor (both
Methuselahs independently, not just the host vampire's own controller).
Built on the real, production `master_phase`/`unlock_phase`/`apply_damage`
call sites, exactly like `tests/cards/test_celerity.py`'s own pattern.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.fame import KRCG_ID
from vtesbot.engine import LibraryCard
from vtesbot.engine.attachments import attach_card, detect_contest_on_attach
from vtesbot.engine.phases.master import master_phase
from vtesbot.engine.phases.unlock import unlock_phase


def _fame_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name="Fame", card_type="master")


def test_registered_as_implemented_against_all_three_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Fame"
    assert reg.blocked_reason is None
    assert set(reg.hooks) == {
        registry.Hook.MASTER_PHASE_PLAY,
        registry.Hook.VAMPIRE_ENTERS_TORPOR,
        registry.Hook.UNLOCK_PHASE_MANDATORY_EFFECT,
    }


# --- Clause: "Put this card on a ready vampire." -----------------------


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_without_any_ready_vampire_anywhere():
    """Only a torpid vampire exists anywhere -- "a ready vampire" excludes
    it (Fame's own text, stricter than Celerity's "a vampire")."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_fame_card())
    p1.torpid_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_attaches_to_own_ready_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p1.hand.append(_fame_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "fame:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    vampire = game.vampire("V1")
    attachments = [a for a in vampire.attachments if a.krcg_id == KRCG_ID]
    assert len(attachments) == 1
    assert attachments[0].zone == "attached"
    assert attachments[0].controller == "P1"
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Fame"]
    agent.assert_exhausted()


def test_can_target_the_opponents_ready_vampire():
    """Rulebook §2 Card Types: "A master card in play is controlled by the
    Methuselah who played it, even if it is played on a card controlled by
    another Methuselah" -- no "you control" qualifier on this card's text."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_fame_card())
    builder.player("P2", pool=30).ready_vampire("V1", capacity=3)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "fame:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    vampire = game.vampire("V1")
    attachment = next(a for a in vampire.attachments if a.krcg_id == KRCG_ID)
    assert vampire.controller == "P2"
    assert attachment.controller == "P1"  # whoever played it, Rulebook §2
    agent.assert_exhausted()


def test_cannot_target_a_torpid_vampire_even_when_a_ready_one_is_also_available():
    """Stricter than Celerity's own targeting (which also allows torpor):
    only the ready vampire is offered, never the torpid one."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_fame_card())
    p1.ready_vampire("Ready1", capacity=3)
    p1.torpid_vampire("Torpid1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "fame:Ready1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert any(a.krcg_id == KRCG_ID for a in game.vampire("Ready1").attachments)
    assert not any(a.krcg_id == KRCG_ID for a in game.vampire("Torpid1").attachments)
    agent.assert_exhausted()


# --- Clause: "Unique." (contest, ENG-014) ---------------------------------


def test_a_second_independently_played_copy_triggers_a_contest_with_no_fame_specific_code():
    """ "Unique" governs contest, not initial legality to play -- nothing
    stops a second, independently-played copy; that is exactly what
    triggers a contest. Built entirely on the generic ENG-014 machinery
    (`attach_card`/`detect_contest_on_attach`), already proven in
    `tests/rules/test_attachment_contests.py`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p1.hand.append(_fame_card())
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
    existing = attach_card(
        game.state, game.vampire("V2"), controller="P2", krcg_id=KRCG_ID, name="Fame"
    )

    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "fame:V1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    incoming = next(a for a in game.vampire("V1").attachments if a.krcg_id == KRCG_ID)
    assert incoming.zone == "contested"
    assert existing.zone == "contested"
    assert incoming.contested_with == existing.instance_id
    assert existing.contested_with == incoming.instance_id
    agent.assert_exhausted()


# --- Clause: "After this vampire goes to torpor, their controller burns 3 pool." ----


def test_the_host_vampires_own_controller_burns_3_pool_when_it_goes_to_torpor():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    attach_card(game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name="Fame")

    game.apply_damage("V1", aggravated=1)  # healthy vampire -> straight to torpor.

    assert game.zone_of("V1") == "torpor"
    assert game.pool_of("P1") == 27


def test_it_is_the_host_vampires_controller_who_burns_not_fames_own_player():
    """Fame's `controller` (whoever played it) may differ from the host
    vampire's own controller -- "their controller" is the vampire's,
    per the card text's own antecedent."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("V1", capacity=3, blood=0)
    game = builder.build()
    attach_card(game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name="Fame")

    game.apply_damage("V1", aggravated=1)

    assert game.pool_of("P2") == 27  # the host vampire's own controller
    assert game.pool_of("P1") == 30  # not Fame's own controller


def test_no_pool_loss_when_a_vampire_without_fame_goes_to_torpor():
    """Zero-regression: the hook fires on every torpor transition, but only
    reacts when Fame is actually attached."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()

    game.apply_damage("V1", aggravated=1)

    assert game.zone_of("V1") == "torpor"
    assert game.pool_of("P1") == 30


def test_no_pool_loss_while_fames_own_attachment_is_contested():
    """A contested copy is face down and out of play (ENG-014): it must not
    react to its host vampire going to torpor."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
    mine = attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name="Fame"
    )
    other = attach_card(
        game.state, game.vampire("V2"), controller="P2", krcg_id=KRCG_ID, name="Fame"
    )
    detect_contest_on_attach(game.state, other)
    assert mine.zone == "contested"

    game.apply_damage("V1", aggravated=1)

    assert game.pool_of("P1") == 30


# --- Clause: "During each Methuselah's unlock phase, if this vampire is
# in torpor, that Methuselah burns 1 pool." ----


def test_fames_own_controllers_unlock_phase_burns_1_pool_while_the_vampire_is_in_torpor():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    attach_card(game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name="Fame")
    game.apply_damage("V1", aggravated=1)
    pool_after_torpor_entry = game.pool_of("P1")
    game.state.agents["P1"] = ScriptedAgent("P1")

    unlock_phase(game.state, "P1")

    assert game.pool_of("P1") == pool_after_torpor_entry - 1


def test_every_methuselahs_own_unlock_phase_burns_1_pool_not_just_the_hosts_controller():
    """ "That Methuselah" refers back to "each Methuselah" -- *both*
    Methuselahs burn 1 pool on their own respective unlock phases, even one
    who controls neither the host vampire nor Fame itself."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("V1", capacity=3, blood=0)
    game = builder.build()
    attach_card(game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name="Fame")
    game.apply_damage("V1", aggravated=1)
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    unlock_phase(game.state, "P1")  # Fame's own controller's unlock phase
    unlock_phase(game.state, "P2")  # the host vampire's own controller's unlock phase

    assert game.pool_of("P1") == 29
    assert game.pool_of("P2") == 26  # 27 (torpor-entry burn) - 1 (unlock-phase burn)


def test_no_unlock_phase_pool_loss_once_the_vampire_leaves_torpor():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    attach_card(game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name="Fame")
    game.apply_damage("V1", aggravated=1)
    game.vampire("V1").zone = "ready"  # left torpor by some other means
    game.state.agents["P1"] = ScriptedAgent("P1")

    unlock_phase(game.state, "P1")

    assert game.pool_of("P1") == 27  # no further loss: only the earlier torpor-entry burn


def test_no_unlock_phase_pool_loss_while_fames_own_attachment_is_contested():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
    mine = attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name="Fame"
    )
    other = attach_card(
        game.state, game.vampire("V2"), controller="P2", krcg_id=KRCG_ID, name="Fame"
    )
    detect_contest_on_attach(game.state, other)
    assert mine.zone == "contested"
    game.vampire("V1").zone = "torpor"
    # P1 still owes the ordinary, Fame-unrelated attachment-contest pay/
    # yield decision (ENG-014's own generic mechanism, already proven in
    # `tests/rules/test_attachment_contest_resolution.py`) -- scripted here
    # only so this test can isolate and assert Fame's *own* unlock hook
    # specifically stays silent while contested.
    agent = ScriptedAgent("P1").expect("attachment_contest_resolution", "pay")
    game.state.agents["P1"] = agent

    unlock_phase(game.state, "P1")

    assert game.pool_of("P1") == 29  # 1 pool lost to the contest pay, 0 to Fame's own hook
    agent.assert_exhausted()


def test_mandatory_pool_burn_coexists_with_another_optional_unlock_effect_in_the_same_phase():
    """The ruling on file: pool payments during the unlock phase can be
    ordered with the acting Methuselah's other unlock effects, but must
    resolve before the impulse passes. Fame's own burn has no legal
    alternative once chosen, but the *order* in which the Methuselah
    chooses it, relative to another, genuinely optional effect (the Edge
    gain), is the player's own call -- both orders reach the same pool
    total, proven here by resolving the Edge gain first."""
    builder = ScenarioBuilder(seed=1).edge_holder("P1")
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    attach_card(game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name="Fame")
    game.apply_damage("V1", aggravated=1)
    agent = ScriptedAgent("P1")
    agent.expect("unlock_phase_order", "edge_gain")
    agent.expect("edge_pool_gain", "gain_pool")
    game.state.agents["P1"] = agent

    unlock_phase(game.state, "P1")

    # 30 - 3 (torpor-entry burn) - 1 (mandatory unlock-phase burn) + 1 (Edge gain) = 27.
    assert game.pool_of("P1") == 27
    agent.assert_exhausted()


def test_mandatory_pool_burn_is_orderable_after_a_contested_cards_own_pay_decision():
    """Regression for a `rules-auditor`-confirmed MAJOR bug: the engine used
    to run Fame's clause-4 burn unconditionally before any other
    unlock-phase effect. At pool 2, with a separate contested vampire whose
    own pay-or-yield decision costs 1 pool, running the mandatory burn
    first dropped pool to 1 before that contest's own affordability gate
    (`can_afford_without_ousting`, DES-009) was ever checked, silently
    removing "pay" from its offered choices even though the ruling
    entitles the acting Methuselah to resolve the contest's own pay first
    and the mandatory burn after. Proven here by scripting exactly that
    order and asserting "pay" is actually offered."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=2).torpid_vampire("V1", capacity=3, blood=0)
    p1.ready_vampire("P1-Contested", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("P2-Contested", capacity=3, blood=1)
    game = builder.build()
    # Attached after `V1` is already in torpor, by direct construction (not via
    # `send_to_torpor`): isolates clause 4 (unlock-phase burn) from clause 3's
    # own torpor-entry burn, which is not this test's own concern.
    attach_card(game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name="Fame")
    assert game.pool_of("P1") == 2
    game.vampire("P1-Contested").contested_with = "P2-Contested"
    game.vampire("P2-Contested").contested_with = "P1-Contested"

    agent = ScriptedAgent("P1")
    agent.expect("unlock_phase_order", "contest:P1-Contested")
    agent.expect("contest_resolution", "pay")
    game.state.agents["P1"] = agent

    unlock_phase(game.state, "P1")

    # 2 - 1 (contest pay, legal only while pool is still 2) - 1 (mandatory Fame burn) = 0.
    assert game.pool_of("P1") == 0
    assert game.vampire("P1-Contested").zone == "ready"  # paid, not yielded
    agent.assert_exhausted()


def test_fame_oust_mid_combat_resolves_the_simultaneous_second_damage_first(monkeypatch):
    """Fame's torpor pool burn queues P1's oust, but both strikes' damage is
    one simultaneous event (DES-010): P2's damage (mend decision included) is
    still resolved, then the oust is decided once. Only P1 is at 0: ordinary
    oust. Nothing is asked after the game ends (sim seeds 270/942)."""
    from vtesbot.engine import combat

    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=3).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3, blood=2)
    game = builder.build()
    game.vampire("V1").wounded = True
    attach_card(game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name="Fame")
    game.state.agents["P1"] = ScriptedAgent("P1")
    p2 = ScriptedAgent("P2")
    p2.expect("mend_damage", "1")
    game.state.agents["P2"] = p2
    monkeypatch.setattr(
        combat, "_resolve_one_strike", lambda *a, **k: (combat.StrikeDamage(1), False)
    )

    combat._resolve_strike_pair(
        game.state, "P2", game.vampire("V2"), "P1", game.vampire("V1"), {}, {}
    )

    assert game.state.game_over is True
    assert game.state.winner == "P2"
    assert game.blood_of("V2") == 1
    p2.assert_exhausted()


def test_fame_double_torpor_in_one_strike_pair_is_a_tie(monkeypatch):
    """Both vampires carry Fame and go to torpor from the same simultaneous
    strike pair, each controller burning 3 from 3 pool: both reach 0 in the
    same event, a tie (DES-010)."""
    from vtesbot.engine import combat

    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=3).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=3).ready_vampire("V2", capacity=3, blood=0)
    game = builder.build()
    for vid, owner in (("V1", "P1"), ("V2", "P2")):
        game.vampire(vid).wounded = True
        attach_card(game.state, game.vampire(vid), controller=owner, krcg_id=KRCG_ID, name="Fame")
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")
    monkeypatch.setattr(
        combat, "_resolve_one_strike", lambda *a, **k: (combat.StrikeDamage(1), False)
    )

    combat._resolve_strike_pair(
        game.state, "P2", game.vampire("V2"), "P1", game.vampire("V1"), {}, {}
    )

    assert game.state.game_over is True
    assert game.state.winner is None
    assert game.state.eliminated == {"P1", "P2"}


def test_fame_double_torpor_with_the_other_side_above_three_pool_is_an_ordinary_oust(
    monkeypatch,
):
    """Same strike pair as the tie test, but P2 has 4 pool: 4 - 3 = 1 survives,
    so only P1 is ousted and P2 wins (the second side's Fame burn is still
    applied inside the deferral window, DES-010)."""
    from vtesbot.engine import combat

    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=3).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=4).ready_vampire("V2", capacity=3, blood=0)
    game = builder.build()
    for vid, owner in (("V1", "P1"), ("V2", "P2")):
        game.vampire(vid).wounded = True
        attach_card(game.state, game.vampire(vid), controller=owner, krcg_id=KRCG_ID, name="Fame")
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")
    monkeypatch.setattr(
        combat, "_resolve_one_strike", lambda *a, **k: (combat.StrikeDamage(1), False)
    )

    combat._resolve_strike_pair(
        game.state, "P2", game.vampire("V2"), "P1", game.vampire("V1"), {}, {}
    )

    assert game.state.game_over is True
    assert game.state.winner == "P2"
    assert game.state.eliminated == {"P1"}
