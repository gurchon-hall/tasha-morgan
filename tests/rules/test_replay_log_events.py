"""Human-readable `"event"` replay-log entries (`engine/log.py::
ReplayLog.record_event`).

Purely additive, observability-only narration on top of the existing
`"decision"`/`"random"` entries (no rule ever reads an `"event"` entry
back) -- added so a `sim/report.py` decision-log transcript can actually
answer "how did this game end?" without a human re-deriving pool/damage/
torpor/oust consequences by hand. Written at the single centralising call
site each mechanism already has (`pool.py::lose_pool`/`gain_pool`,
`damage.py::apply_damage`/`send_to_torpor`/`burn_vampire`,
`ousting.py::check_oust`), so every one of their existing callers gets it
for free with no call-site changes.
"""

from helpers import ScenarioBuilder
from vtesbot.engine.damage import apply_damage, burn_vampire, send_to_torpor
from vtesbot.engine.ousting import check_oust
from vtesbot.engine.pool import gain_pool, lose_pool


def _event_descriptions(log) -> list[str]:
    return [e.data["description"] for e in log.entries if e.kind == "event"]


def test_lose_pool_records_an_event():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=10).build()

    lose_pool(game.state, "P1", 3)

    assert "P1 loses 3 pool (now 7)" in _event_descriptions(game.state.log)


def test_losing_zero_pool_records_no_event():
    game = ScenarioBuilder(seed=1).player("P1", pool=5).player("P2", pool=10).build()

    lose_pool(game.state, "P1", 0)  # non-positive amount: early-return, no-op

    assert _event_descriptions(game.state.log) == []


def test_gain_pool_records_an_event():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=10).build()

    gain_pool(game.state, "P1", 4)

    assert "P1 gains 4 pool (now 14)" in _event_descriptions(game.state.log)


def test_check_oust_records_an_event():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=0).build()

    check_oust(game.state, "P2")

    descriptions = _event_descriptions(game.state.log)
    assert any("P2 is OUSTED" in d and "P1 wins" in d for d in descriptions)


def test_apply_damage_records_a_summary_event():
    # blood=0 (the default): no blood to mend with, so no mend `Decision`
    # is raised -- keeps this test focused on the logged event, not mending.
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10).ready_vampire("V1")
    builder.player("P2", pool=10)
    game = builder.build()
    vampire = game.vampire("V1")

    apply_damage(game.state, "P1", vampire, normal=1)

    assert any(
        "takes 1 normal + 0 aggravated damage" in d for d in _event_descriptions(game.state.log)
    )


def test_send_to_torpor_records_an_event():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10).ready_vampire("V1", name="Fred")
    builder.player("P2", pool=10)
    game = builder.build()
    vampire = game.vampire("V1")

    send_to_torpor(game.state, "P1", vampire)

    assert any("Fred" in d and "enters torpor" in d for d in _event_descriptions(game.state.log))


def test_burn_vampire_records_an_event():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10).ready_vampire("V1", name="Fred")
    builder.player("P2", pool=10)
    game = builder.build()
    vampire = game.vampire("V1")

    burn_vampire(game.state, "P1", vampire)

    assert any("Fred" in d and "is burned" in d for d in _event_descriptions(game.state.log))
