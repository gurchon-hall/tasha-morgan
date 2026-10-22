"""`cards/common.py` discipline helpers: printed level, lowercase codes only."""

import pytest

from helpers import ScenarioBuilder
from vtesbot.cards.common import discipline_level, has_discipline


def _vampire(disciplines: tuple[str, ...]):
    builder = ScenarioBuilder(seed=1)
    builder.player("P1").ready_vampire("V1", disciplines=disciplines)
    builder.player("P2")
    return builder.build().vampire("V1")


def test_levels():
    assert discipline_level(_vampire(()), "cel") == 0
    assert discipline_level(_vampire(("cel",)), "cel") == 1
    assert discipline_level(_vampire(("CEL",)), "cel") == 2


def test_basic_vampire_is_not_superior():
    vampire = _vampire(("cel",))
    assert has_discipline(vampire, "cel")
    assert discipline_level(vampire, "cel") < 2


def test_uppercase_code_is_rejected():
    with pytest.raises(ValueError, match="lowercase"):
        has_discipline(_vampire(("cel",)), "CEL")
