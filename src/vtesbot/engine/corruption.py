"""Corruption counters on a vampire (`VampireInPlay.corruption_counters`, keyed by
placer). Distinct from `engine/cards.py::CardAttachment.counters`; see that field's
own docstring and `VampireInPlay.corruption_counters`'s own docstring for the sources
establishing the distinction (Aniel 201666, Sergio Bueno 201662, The Platinum
Protocol 102232)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import VampireInPlay


def add_corruption_counters(vampire: VampireInPlay, placer: str, amount: int) -> int:
    """Place `amount` corruption counters from `placer` onto `vampire` (e.g. The
    Platinum Protocol, krcg 102232: "Put 1 corruption counter on a minion controlled
    by the target Methuselah..."). No cap: the printed cards place counters freely --
    only *burning* a counter is a floor-at-zero operation (`burn_corruption_counters`
    below). Returns the amount actually added (always `amount` when positive, mirroring
    `engine/damage.py::add_blood`/`engine/allies.py::add_life`'s own "return the amount
    actually applied" convention)."""
    if amount <= 0:
        return 0
    vampire.corruption_counters[placer] = vampire.corruption_counters.get(placer, 0) + amount
    return amount


def burn_corruption_counters(vampire: VampireInPlay, placer: str, amount: int) -> int:
    """Burn up to `amount` of `vampire`'s corruption counters placed by `placer`,
    floored at zero -- mirrors `engine/damage.py::add_blood`/`engine/allies.py::
    add_life`'s own capped-helper shape (there, capped above by a maximum; here,
    capped below by what is actually present). Returns the amount actually burned.
    A placer with no counters recorded is removed from the dict entirely rather than
    left at `0`, so `total_corruption_counters`/a `placer in vampire.corruption_
    counters` check never sees a stale zero entry."""
    if amount <= 0:
        return 0
    current = vampire.corruption_counters.get(placer, 0)
    burned = min(amount, current)
    if burned <= 0:
        return 0
    remaining = current - burned
    if remaining:
        vampire.corruption_counters[placer] = remaining
    else:
        del vampire.corruption_counters[placer]
    return burned


def total_corruption_counters(vampire: VampireInPlay) -> int:
    """Sum of `vampire`'s corruption counters across every placer (e.g. Aniel, krcg
    201666: "burn 1 corruption counter... from another ready minion" -- generic,
    not scoped to a specific placer, unlike Sergio Bueno's own "YOUR corruption
    counters")."""
    return sum(vampire.corruption_counters.values())
