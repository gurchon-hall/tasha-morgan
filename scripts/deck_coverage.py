"""Report missing (not-yet-implemented) cards per VEKN 2P decklist fixture,
and a greedy card-implementation order that unlocks the most decks for the
fewest cards implemented.

Greedy rule: repeatedly finish whichever not-yet-playable deck currently
needs the fewest still-missing distinct cards (counting only cards not
already implemented by an earlier step, since cards are shared across
decks). This is the standard heuristic for minimizing cumulative cost to
unlock the most sets when set costs overlap: it never spends cards on a
more expensive deck while a cheaper one remains unfinished. Finding the
true cost-optimal order is a weighted set-cover variant (NP-hard in
general); this greedy is a practical approximation, not a proof of
optimality.

Usage:
    python scripts/deck_coverage.py [--decks-dir data/decks/vekn-2p]
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_decks(decks_dir: Path) -> dict[str, dict[int, tuple[str, str | None]]]:
    decks: dict[str, dict[int, tuple[str, str | None]]] = {}
    for path in sorted(decks_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cards: dict[int, tuple[str, str | None]] = {}
        for card in data.get("crypt", []) + data.get("library", []):
            cards[card["krcg_id"]] = (card["name"], card.get("implementation_status"))
        decks[path.stem] = cards
    return decks


def missing_cards(cards: dict[int, tuple[str, str | None]]) -> dict[int, str]:
    return {kid: name for kid, (name, status) in cards.items() if status != "implemented"}


def greedy_sequence(
    missing_by_deck: dict[str, dict[int, str]],
) -> list[tuple[list[str], dict[int, str], int, int]]:
    """Returns one entry per step: (decks unlocked, newly implemented cards,
    cumulative cards implemented, decks playable so far)."""
    remaining = {name: dict(cards) for name, cards in missing_by_deck.items()}
    implemented_ids: set[int] = set()
    done: set[str] = set()
    cumulative = 0
    steps: list[tuple[list[str], dict[int, str], int, int]] = []

    while len(done) < len(remaining):
        pending = {name: cards for name, cards in remaining.items() if name not in done}
        costs = {
            name: {kid: n for kid, n in cards.items() if kid not in implemented_ids}
            for name, cards in pending.items()
        }
        target, new_cards = min(costs.items(), key=lambda kv: (len(kv[1]), kv[0]))
        cumulative += len(new_cards)
        implemented_ids |= set(new_cards)
        done.add(target)

        unlocked = [target]
        for other, cards in pending.items():
            if other != target and all(kid in implemented_ids for kid in cards):
                done.add(other)
                unlocked.append(other)

        steps.append((unlocked, new_cards, cumulative, len(done)))

    return steps


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decks-dir",
        type=Path,
        default=ROOT / "data" / "decks" / "vekn-2p",
    )
    args = parser.parse_args()

    decks = load_decks(args.decks_dir)
    missing_by_deck = {name: missing_cards(cards) for name, cards in decks.items()}

    print("=== Missing (not_implemented) cards per deck ===")
    for name in sorted(missing_by_deck):
        print(f"{name:40s} {len(missing_by_deck[name]):2d} missing / {len(decks[name]):2d} total")

    print()
    print("=== Greedy sequence (finish cheapest remaining deck first) ===")
    for step, (unlocked, new_cards, cumulative, playable) in enumerate(
        greedy_sequence(missing_by_deck), start=1
    ):
        target, *bonus = unlocked
        suffix = f" + bonus {bonus}" if bonus else ""
        print(
            f"Step {step:2d}: implement {len(new_cards):2d} card(s) -> unlocks '{target}'{suffix} "
            f"(cumulative cards implemented: {cumulative}, decks playable: {playable}/{len(decks)})"
        )
        if new_cards:
            print(f"          new cards: {'; '.join(sorted(new_cards.values()))}")

    distinct_total = len({kid for m in missing_by_deck.values() for kid in m})
    print()
    print(f"Distinct cards still to implement to unlock ALL {len(decks)} decks: {distinct_total}")


if __name__ == "__main__":
    main()
