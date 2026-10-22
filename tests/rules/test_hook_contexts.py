"""`engine/hook_contexts.py`: every wired hook declares its context, and every
dispatch is checked against it (missing or undeclared keys raise)."""

import pytest

from helpers import ScenarioBuilder
from vtesbot.engine import hooks
from vtesbot.engine.hook_contexts import HOOK_CONTEXTS, OPEN_CONTEXTS, check_context
from vtesbot.engine.hooks import UNWIRED_HOOKS, Hook


@pytest.fixture
def game_state():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    return builder.build().state


def test_every_wired_hook_and_only_those_declare_a_context():
    assert set(HOOK_CONTEXTS) == set(Hook) - UNWIRED_HOOKS


def test_exact_context_passes():
    check_context(Hook.CAPACITY_MODIFIER, {"vampire": "V1"})


def test_missing_key_raises():
    with pytest.raises(TypeError, match="CapacityModifierContext"):
        check_context(Hook.CAPACITY_MODIFIER, {})


def test_undeclared_key_raises():
    with pytest.raises(TypeError, match="fit none of"):
        check_context(Hook.CAPACITY_MODIFIER, {"vampire": "V1", "player": "P1"})


def test_a_two_phase_hook_accepts_either_phase_and_nothing_else():
    before = {"player": "P1", "phase": "before_cast", "caller": "P1"}
    before |= {"caller_vampire_id": "V1", "pending": {}}
    check_context(Hook.POLLING_STEP, before)
    mid = before | {"phase": "mid_cast", "other": "P2", "votes_for": 0, "votes_against": 0}
    check_context(Hook.POLLING_STEP, mid | {"casts": []})
    with pytest.raises(TypeError):
        check_context(Hook.POLLING_STEP, mid)  # mid-cast keys without `casts`


def test_open_context_allows_extra_keys_but_not_missing_ones():
    assert Hook.CANCEL_AS_PLAYED in OPEN_CONTEXTS
    required = {
        "player": "P2",
        "canceled_by": "P1",
        "canceled_choice": "x",
        "canceled_card_type": None,
    }
    check_context(Hook.CANCEL_AS_PLAYED, required | {"pending": {}, "vampire": "V1"})
    with pytest.raises(TypeError):
        check_context(Hook.CANCEL_AS_PLAYED, {"player": "P2"})


def test_unwired_hook_has_no_context_to_dispatch_with():
    with pytest.raises(TypeError, match="UNWIRED_HOOKS"):
        check_context(Hook.RANGED_STRIKE, {})


@pytest.mark.parametrize(
    ("dispatch", "hook"),
    [
        (hooks.offer, Hook.MASTER_PHASE_PLAY),
        (hooks.sum_modifiers, Hook.CAPACITY_MODIFIER),
        (hooks.run_effects, Hook.VAMPIRE_ENTERS_TORPOR),
        (hooks.any_true, Hook.CANNOT_HUNT),
        (hooks.collect, Hook.BLOCK_ATTEMPT_COST),
        (hooks.union_modifiers, Hook.DISCIPLINE_LEVEL_MODIFIER),
    ],
)
def test_every_dispatcher_checks_the_context(game_state, dispatch, hook):
    with pytest.raises(TypeError):
        dispatch(hook, game_state, unexpected_key=1)


def test_a_test_local_hook_name_is_not_checked(game_state):
    assert hooks.offer("fake_local_hook", game_state, anything=1) == []  # type: ignore[arg-type]
