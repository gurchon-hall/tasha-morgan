"""Loads one versioned VEKN 2-player allowed-card-list file.

CLAUDE.md SS4: "2P allowed list: stored as `data/formats/2p/<YYYY-MM-DD>.json`
... The active version is selected by config, never implicit." Accordingly
`load_allowed_list` always takes an explicit path -- callers decide which
dated file is active (e.g. a CLI flag, a test fixture), the same contract
`scripts/validate_deck.py --format <path>` already enforces for the dev
tooling this module's checks were ported from.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AllowedCard:
    """One entry on the allowed list: `data/formats/2p/<date>.json`'s own
    `{"name", "type", "krcg_id"}` shape. `type` is `"Crypt"` or a single
    library type string (`"Master"`, `"Action"`, `"Political Action"`, ...)."""

    krcg_id: int
    name: str
    type: str


@dataclass(frozen=True)
class AllowedList:
    vekn_last_updated: str
    source: str
    by_krcg_id: Mapping[int, AllowedCard]


def load_allowed_list(path: Path | str) -> AllowedList:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    by_krcg_id = {
        c["krcg_id"]: AllowedCard(krcg_id=c["krcg_id"], name=c["name"], type=c["type"])
        for c in raw["cards"]
    }
    return AllowedList(
        vekn_last_updated=raw["vekn_last_updated"], source=raw["source"], by_krcg_id=by_krcg_id
    )
