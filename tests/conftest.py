import pytest

from vtesbot.engine import hooks


@pytest.fixture(autouse=True)
def _isolate_hook_registry():
    """Test isolation (CLAUDE.md "no global state"/DES-005):
    the hook catalogue (`engine/hooks.py`) is shared, process-wide, static
    state, so a fake provider a test registers must not leak into the next
    one. Snapshot/restore, not a blanket `hooks.clear()`: the catalogue also
    holds every *real* card's providers, registered once at import time by
    `vtesbot.cards` -- a blanket clear wipes those too, and nothing re-runs
    their module-level `register()` calls to bring them back, silently
    turning every later test's real card providers into no-ops for the rest
    of the process (found by `rules-auditor` reviewing ENG-030: 31 files under
    `tests/rules/` each had their own `hooks.clear()`-based copy of this
    fixture, order-dependent and unsafe under any subset/`-k` run, only
    accidentally safe under a full default `pytest` run)."""
    snapshot = hooks.snapshot()
    yield
    hooks.restore(snapshot)
