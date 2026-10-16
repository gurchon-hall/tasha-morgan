"""`engine/phases/minion.py::ATTACHMENT_REMOVAL_ACTION_HOOK`/
`build_attachment_removal_action_spec`: a generic "+1 stealth action,
cumulative across either side's vampires, removes a named attachment once
N total contributions have been made" minion action, offered alongside
`ACTION_CARD_PLAY_HOOK`/`RECRUIT_ALLY_PLAY_HOOK` in `_choose_and_perform_
action`'s own default action list.

Sourced from Pulled Fangs (krcg 101515): "Any vampire(s) can burn this card
with two +1 stealth actions."; ruling "A total of two actions must be
performed (by whomever) to remove it. Vampires A and B can both take the
action, then it is removed." [ANK 20170202-2] (confirming a blocked
attempt does not contribute, and either side's vampire may contribute).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake attachment (sentinel `krcg_id`, mirrors
`tests/rules/test_attachments.py`'s own convention) and
`contributions_required=2` to match Pulled Fangs' own text, without wiring
that card for real -- that remains `card-implementer`'s job once this
capability exists; it stays registered `blocked` until then.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_ATTACHMENT_REMOVAL
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import (
    ATTACHMENT_REMOVAL_ACTION_HOOK,
    ATTACHMENT_REMOVAL_STEALTH,
    build_attachment_removal_action_spec,
    minion_phase,
)

FAKE_ATTACHMENT_KRCG_ID = 999999


# --- Direct tests of build_attachment_removal_action_spec's own resolve semantics ---


def test_single_contribution_does_not_burn_the_attachment():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    attachment = attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=FAKE_ATTACHMENT_KRCG_ID, name="X"
    )
    spec = build_attachment_removal_action_spec(attachment, contributions_required=2)

    assert spec.base_stealth == ATTACHMENT_REMOVAL_STEALTH
    assert spec.directed is False
    assert spec.action == ACTION_ATTACHMENT_REMOVAL

    spec.resolve({})

    assert attachment.counters == 1
    assert attachment.zone == "attached"


def test_second_contribution_burns_the_attachment():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    attachment = attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=FAKE_ATTACHMENT_KRCG_ID, name="X"
    )
    spec = build_attachment_removal_action_spec(attachment, contributions_required=2)

    spec.resolve({})  # first contribution (e.g. by vampire A)
    spec.resolve({})  # second contribution (e.g. by vampire B)

    assert attachment.counters == 2
    assert attachment.zone == "burned"


def test_resolve_fizzles_once_the_attachment_has_already_been_removed():
    """OQ-21 convention: a contribution that resolves after the attachment
    is already gone (e.g. a different, earlier-resolving contribution
    already burned it this same round) is simply a no-op, not an error and
    not an over-count."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    attachment = attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=FAKE_ATTACHMENT_KRCG_ID, name="X"
    )
    spec = build_attachment_removal_action_spec(attachment, contributions_required=2)
    attachment.zone = "burned"  # already removed by some other means

    spec.resolve({})

    assert attachment.counters is None  # untouched: resolve never ran its body


# --- End-to-end through minion_phase/_choose_and_perform_action -------------------


def _fake_attachment_removal_provider(state, context):
    """Stand-in for a future Pulled Fangs-style provider: offers removing
    the one fake attachment, for any acting vampire of either player."""
    vampire_id = context["vampire"]
    for player_state in state.players.values():
        for host in player_state.vampires.values():
            for attachment in host.attachments:
                if attachment.krcg_id == FAKE_ATTACHMENT_KRCG_ID and attachment.zone == "attached":

                    def _apply(s, a=attachment):
                        del s
                        return build_attachment_removal_action_spec(a, contributions_required=2)

                    return [
                        hooks.HookOption(
                            choice=Choice(
                                f"remove_fake_attachment:{vampire_id}", "Contribute to removal"
                            ),
                            apply=_apply,
                        )
                    ]
    return []


def test_offered_as_a_default_action_and_blockable():
    """Wired into `_choose_and_perform_action`'s own default action list;
    an undirected action, so the sole 2P opponent may attempt to block it
    like any other (CLAUDE.md §3)."""
    hooks.register(ATTACHMENT_REMOVAL_ACTION_HOOK, _fake_attachment_removal_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    attachment = attach_card(
        game.state, game.vampire("B1"), controller="P2", krcg_id=FAKE_ATTACHMENT_KRCG_ID, name="X"
    )
    v1_id = game.vampire("V1").instance_id
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", f"remove_fake_attachment:{v1_id}")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # exercises its right to block
    defender.expect("block_attempt", "decline")  # stealth 1 > intercept 0: fails, then declines
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert attachment.counters == 1
    assert attachment.zone == "attached"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_either_side_contributes_two_contributions_total_burns_it():
    """Ruling [ANK 20170202-2]: vampires A and B (here, both P1's own
    vampires -- "any vampire(s)", not only the attachment's own
    controller's) can each take the action; once two total have
    succeeded, the attachment is removed."""
    hooks.register(ATTACHMENT_REMOVAL_ACTION_HOOK, _fake_attachment_removal_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1).ready_vampire(
        "V2", capacity=3, blood=1
    )
    builder.player("P2", pool=30)  # no ready vampire: unblockable
    game = builder.build()
    attachment = attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=FAKE_ATTACHMENT_KRCG_ID, name="X"
    )
    v1_id = game.vampire("V1").instance_id
    v2_id = game.vampire("V2").instance_id
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", f"remove_fake_attachment:{v1_id}")
    actor.expect("minion_phase_choice", "act_with:V2")
    actor.expect("action_choice", f"remove_fake_attachment:{v2_id}")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert attachment.zone == "burned"
    assert attachment.counters == 2
    actor.assert_exhausted()


def test_blocked_contribution_does_not_count():
    """A successfully blocked attempt never reaches `resolve()` -- no
    contribution is recorded (`perform_minion_action`'s own blocked
    branch never calls `resolve`)."""
    hooks.register(ATTACHMENT_REMOVAL_ACTION_HOOK, _fake_attachment_removal_provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    attachment = attach_card(
        game.state, game.vampire("B1"), controller="P2", krcg_id=FAKE_ATTACHMENT_KRCG_ID, name="X"
    )
    v1_id = game.vampire("V1").instance_id
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", f"remove_fake_attachment:{v1_id}")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")

    def intercept_provider(state, context):
        if context.get("player") != "P2":
            return []
        return [hooks.HookOption(choice=Choice("use_intercept", "+5 intercept"), apply=lambda s: 5)]

    hooks.register("intercept_modifier", intercept_provider)
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("intercept_modifier", "use_intercept")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert attachment.counters is None  # resolve() never ran at all
    assert attachment.zone == "attached"
    actor.assert_exhausted()
    defender.assert_exhausted()
