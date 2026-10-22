"""`cards/common.py` discipline helpers: effective level, lowercase codes only."""

import pytest

from helpers import ScenarioBuilder
from vtesbot.cards.celerity import KRCG_ID as CELERITY_ID
from vtesbot.cards.common import discipline_level, has_discipline
from vtesbot.engine.cards import CardAttachment


def _vampire(disciplines: tuple[str, ...]):
    builder = ScenarioBuilder(seed=1)
    builder.player("P1").ready_vampire("V1", disciplines=disciplines)
    builder.player("P2")
    game = builder.build()
    return game.state, game.vampire("V1")


def test_levels():
    assert discipline_level(*_vampire(()), "cel") == 0
    assert discipline_level(*_vampire(("cel",)), "cel") == 1
    assert discipline_level(*_vampire(("CEL",)), "cel") == 2


def test_basic_vampire_is_not_superior():
    state, vampire = _vampire(("cel",))
    assert has_discipline(state, vampire, "cel")
    assert discipline_level(state, vampire, "cel") < 2


def test_uppercase_code_is_rejected():
    with pytest.raises(ValueError, match="lowercase"):
        has_discipline(*_vampire(("cel",)), "CEL")


def test_attached_celerity_counts():
    """ENG-047: a discipline granted by an attachment counts like a printed one."""
    state, vampire = _vampire(("pot",))
    vampire.attachments.append(CardAttachment(krcg_id=CELERITY_ID, name="Celerity"))
    assert discipline_level(state, vampire, "cel") == 1
    vampire.attachments.append(CardAttachment(krcg_id=CELERITY_ID, name="Celerity"))
    assert discipline_level(state, vampire, "cel") == 2
