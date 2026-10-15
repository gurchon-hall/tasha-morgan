"""Enter-combat grant primitive: a crypt card's own printed "during your
master phase" ability (e.g. Lucinde, Alastor: "During your master phase,
Lucinde can burn 1 blood to choose a vampire; this turn, Camarilla
vampires you control can enter combat with the chosen vampire as a Ⓓ
action.") must (1) activate outside the master phase's own
`actions_remaining` economy (Rulebook §4 Master Phase: "If other effects
happen during your master phase, you choose the order in which these
effects and your master phase actions are performed" -- an "other
effect", not an "action") and (2) grant *other* vampires a one-turn
directed "enter combat with the chosen target" option with no card played
(`engine/phases/minion.py::EnterCombatGrant`/
`grant_enter_combat_this_turn`/`active_enter_combat_grants`/
`build_enter_combat_action_spec`).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake crypt-ability provider (not the real
Lucinde, Alastor card, which does not exist yet -- `card-implementer`'s
job once this primitive exists). Mirrors how `engine/combat.py::
commit_strike_for_round` was proven generically by its own engine-level
tests before `cards/slam.py` became its first production user.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.master import (
    MASTER_PHASE_ABILITY_HOOK,
    MASTER_PHASE_PLAY_HOOK,
    master_phase,
)
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    active_enter_combat_grants,
    build_enter_combat_action_spec,
    grant_enter_combat_this_turn,
    minion_phase,
)

ABILITY_CHOICE_VALUE = "fake_lucinde_ability"
GRANTED_ACTION_CHOICE_PREFIX = "fake_granted_enter_combat"
PLAY_CHOICE_VALUE = "fake_master_card_play"


def _build_scenario():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("Lucinde", capacity=10, blood=1).ready_vampire(
        "V1", capacity=6, blood=1
    )
    builder.player("P2", pool=30).ready_vampire("B1", capacity=10, blood=0)
    return builder.build()


def _provide_fake_master_phase_ability(state, context):
    """Stand-in for a real crypt card's own `"master_phase_ability"`
    provider (e.g. a future `lucinde_alastor.py`): offers one option while
    the fake vampire is ready and unlocked, naming the opponent's sole
    vampire as the chosen target."""
    player = context["player"]
    vampire = state.players[player].vampires.get("Lucinde")
    if vampire is None or not vampire.is_ready_unlocked:
        return []

    def _apply(s):
        opponent = s.other_player(player)
        target = next(iter(s.players[opponent].vampires.values()))
        grant_enter_combat_this_turn(
            s, player, target_player=opponent, target_vampire_id=target.instance_id
        )
        return False  # irrelevant return value: never read for an ability option.

    return [hooks.HookOption(choice=Choice(ABILITY_CHOICE_VALUE, "Activate ability"), apply=_apply)]


FAKE_MASTER_CARD_KRCG_ID = -1
"""Sentinel `krcg_id` for `_provide_fake_master_phase_play` below -- not a
real card, only a key into `PlayerState.card_played_turn` (the same
generic "only one X per turn" scratch dict `cards/loup.py` uses for its
own "only one Loup per turn" limit)."""


def _provide_fake_master_phase_play(state, context):
    """Stand-in for an ordinary Master-type library card play, competing
    for the phase's own `actions_remaining` economy -- offered once per
    turn, consumed when played. Used only to prove the ability path
    genuinely leaves this economy untouched (see the test below): if the
    ability wrongly consumed `actions_remaining`, this option would vanish
    after the ability fires instead of remaining offered."""
    player = context["player"]
    if state.players[player].card_played_turn.get(FAKE_MASTER_CARD_KRCG_ID) == state.turn_number:
        return []

    def _apply(s):
        s.players[player].card_played_turn[FAKE_MASTER_CARD_KRCG_ID] = s.turn_number
        return False  # not a trifle.

    return [
        hooks.HookOption(choice=Choice(PLAY_CHOICE_VALUE, "Play fake master card"), apply=_apply)
    ]


def _provide_fake_granted_enter_combat(state, context):
    """Stand-in for the card-specific `ACTION_CARD_PLAY_HOOK` provider any
    future "grant other vampires an enter-combat option" card would
    register: reads `active_enter_combat_grants`, applies its own
    eligibility gate (omitted here -- see module docstring; a real card,
    e.g. Lucinde, would gate on `Sect.CAMARILLA` the same way `cards/
    line_brawl.py` gates on `Sect.ANARCH`), and -- mirroring `line_brawl.py`'s
    own `_eligible_combat_targets` guard -- only offers the option while the
    grant's target is still `zone == "ready"` right now."""
    player = context["player"]
    vampire = state.players[player].vampires.get(context["vampire"])
    if vampire is None:
        return []
    options = []
    for grant in active_enter_combat_grants(state, player):
        target = state.players[grant.target_player].vampires.get(grant.target_vampire_id)
        if target is None or target.zone != "ready":
            continue  # never offer a play that cannot resolve (line_brawl.py precedent).

        def _apply(s, g=grant, v=vampire):
            return build_enter_combat_action_spec(
                s, player, v, g.target_player, g.target_vampire_id
            )

        options.append(
            hooks.HookOption(
                choice=Choice(
                    f"{GRANTED_ACTION_CHOICE_PREFIX}:{vampire.instance_id}:{grant.target_vampire_id}",
                    f"Enter combat with {grant.target_vampire_id} (granted)",
                ),
                apply=_apply,
            )
        )
    return options


def test_ability_is_offered_and_does_not_consume_the_master_phase_action():
    """The base master phase action (1, no trifle) is still available
    *and usable for an actual play* after activating the ability --
    proving the ability is additional to, not drawn from,
    `actions_remaining`. A competing `MASTER_PHASE_PLAY_HOOK` provider is
    registered so this is checked by actually playing it, not merely by
    the ability-only decision happening to also offer "pass" (which would
    pass whether or not `actions_remaining` had been wrongly decremented)."""
    hooks.register(MASTER_PHASE_ABILITY_HOOK, _provide_fake_master_phase_ability)
    hooks.register(MASTER_PHASE_PLAY_HOOK, _provide_fake_master_phase_play)
    game = _build_scenario()

    agent = ScriptedAgent("P1")
    # Both the ability and the competing play option are offered on the
    # very first iteration; activate the ability first.
    agent.expect("master_phase_action", ABILITY_CHOICE_VALUE)
    # The base master phase action must still be there for the play --
    # this is the assertion that actually distinguishes "untouched" from
    # "wrongly decremented to 0".
    agent.expect("master_phase_action", PLAY_CHOICE_VALUE)
    # Action economy now spent (by the play, not the ability): only
    # "pass" has any effect left to offer here (the ability itself has no
    # once-per-turn cap of its own -- see its docstring -- but declining
    # it is always legal).
    agent.expect("master_phase_action", "pass")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()
    assert len(active_enter_combat_grants(game.state, "P1")) == 1
    assert game.state.players["P1"].card_played_turn[FAKE_MASTER_CARD_KRCG_ID] == (
        game.state.turn_number
    )


def test_ability_not_offered_leaves_master_phase_byte_for_byte_unchanged():
    """Zero-regression check: with no ability registered, a bare master
    phase with nothing to play raises no decision at all."""
    game = _build_scenario()
    agent = ScriptedAgent("P1")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_granted_vampire_gets_a_one_turn_enter_combat_option_unblocked():
    """End-to-end: Lucinde-like activation during the master phase grants
    a *different* vampire (V1) a one-turn enter-combat option during the
    minion phase, targeting the chosen vampire (B1); unblocked, it
    initiates combat directly via `run_combat`."""
    hooks.register(MASTER_PHASE_ABILITY_HOOK, _provide_fake_master_phase_ability)
    hooks.register(ACTION_CARD_PLAY_HOOK, _provide_fake_granted_enter_combat)
    game = _build_scenario()

    master_agent = ScriptedAgent("P1")
    master_agent.expect("master_phase_action", ABILITY_CHOICE_VALUE)
    master_agent.expect("master_phase_action", "pass")
    game.state.agents["P1"] = master_agent
    master_phase(game.state, "P1")
    master_agent.assert_exhausted()

    target_id = game.vampire("B1").instance_id
    granted_value = f"{GRANTED_ACTION_CHOICE_PREFIX}:{game.vampire('V1').instance_id}:{target_id}"

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", granted_value)
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    actor.expect("minion_phase_choice", "end_minion_phase")  # Lucinde stays ready/unlocked
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")  # P2 is the defender of V1's own action
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    actor.assert_exhausted()
    defender.assert_exhausted()


def test_granted_vampire_blocked_goes_through_the_generic_combat_path():
    """Blocked branch: the opponent blocks with B1; `perform_minion_action`'s
    own internal `run_combat` call handles it, the granted option's own
    `resolve()` never runs -- same split `line_brawl.py`'s `[pot]` clause
    and `test_pre_combat_maneuver_grant.py` both rely on."""
    hooks.register(MASTER_PHASE_ABILITY_HOOK, _provide_fake_master_phase_ability)
    hooks.register(ACTION_CARD_PLAY_HOOK, _provide_fake_granted_enter_combat)
    game = _build_scenario()

    master_agent = ScriptedAgent("P1")
    master_agent.expect("master_phase_action", ABILITY_CHOICE_VALUE)
    master_agent.expect("master_phase_action", "pass")
    game.state.agents["P1"] = master_agent
    master_phase(game.state, "P1")
    master_agent.assert_exhausted()

    target_id = game.vampire("B1").instance_id
    granted_value = f"{GRANTED_ACTION_CHOICE_PREFIX}:{game.vampire('V1').instance_id}:{target_id}"

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", granted_value)
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    actor.expect("minion_phase_choice", "end_minion_phase")  # Lucinde stays ready/unlocked
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    actor.assert_exhausted()
    defender.assert_exhausted()


def test_grant_does_not_survive_into_a_later_turn():
    """`active_enter_combat_grants` filters by `GameState.turn_number`:
    once the turn advances, the same grant is no longer active, and the
    granted option is not offered."""
    hooks.register(MASTER_PHASE_ABILITY_HOOK, _provide_fake_master_phase_ability)
    hooks.register(ACTION_CARD_PLAY_HOOK, _provide_fake_granted_enter_combat)
    game = _build_scenario()

    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", ABILITY_CHOICE_VALUE)
    agent.expect("master_phase_action", "pass")
    game.state.agents["P1"] = agent
    master_phase(game.state, "P1")
    agent.assert_exhausted()
    assert len(active_enter_combat_grants(game.state, "P1")) == 1

    game.state.turn_number += 1  # simulate the turn having advanced

    assert active_enter_combat_grants(game.state, "P1") == []
    options = hooks.offer(
        ACTION_CARD_PLAY_HOOK,
        game.state,
        player="P1",
        vampire=game.vampire("V1").instance_id,
    )
    assert options == []


def test_granted_option_not_offered_once_target_leaves_ready():
    """Mirrors `cards/line_brawl.py`'s own `_eligible_combat_targets` guard
    (module docstring): if the chosen target has already left `zone ==
    "ready"` by the time a Camarilla (here: any) vampire's own minion
    action is offered, the granted option must not appear at all."""
    hooks.register(MASTER_PHASE_ABILITY_HOOK, _provide_fake_master_phase_ability)
    hooks.register(ACTION_CARD_PLAY_HOOK, _provide_fake_granted_enter_combat)
    game = _build_scenario()

    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", ABILITY_CHOICE_VALUE)
    agent.expect("master_phase_action", "pass")
    game.state.agents["P1"] = agent
    master_phase(game.state, "P1")
    agent.assert_exhausted()

    game.vampire("B1").zone = "torpor"  # target no longer ready

    options = hooks.offer(
        ACTION_CARD_PLAY_HOOK,
        game.state,
        player="P1",
        vampire=game.vampire("V1").instance_id,
    )
    assert options == []
