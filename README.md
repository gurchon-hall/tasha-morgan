# VtES Duel Bot

A bot that plays **Vampire: The Eternal Struggle** in the official
**VEKN two-player variant** (see
[two-player format](https://www.vekn.net/two-player-format)). Reliability
comes before strength: the first milestone is a bot that always plays
legally and never mis-resolves a card. See [CLAUDE.md](CLAUDE.md) for the
full scope, sources-of-truth hierarchy and architecture.

## Status

Milestone 1-5 work is in progress (CLAUDE.md §9): the rules engine, a
random-legal agent and a heuristic agent exist, and the active 2P allowed
list (`data/formats/2p/2026-10-03.json`, 311 cards) is partially
implemented (46 cards + the generic engine rules cover the rest of a
legal game). There is **no CLI yet** (milestone 2/§8's "digital, CLI
first" default is not yet built) — the engine is driven today through
`pytest` scenarios and the scripts below.

## Installation

Requires Python >= 3.14 and [`uv`](https://docs.astral.sh/uv/).

```sh
uv sync
```

This installs both the runtime dependency (`krcg`) and the dev tools
(`pytest`, `ruff`, `pymarkdownlnt`, `pre-commit-hooks`) into `.venv`.

## Running the checks

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pymarkdown scan docs/ CLAUDE.md
uv run pretty-format-json --no-sort-keys --no-ensure-ascii $(find data -name '*.json')
```

The last two only matter when a change touches a tracked `.md` file or
anything under `data/` (CLAUDE.md §6).

## Running a bot-vs-bot simulation

Validate a decklist fixture against the active 2P allowed list:

```sh
uv run python scripts/validate_deck.py data/decks/vekn-2p/brujah.json \
    --format data/formats/2p/2026-10-03.json
```

Run a batch of seat-alternated games between two deck/agent pairs
(available decks: `brujah`, `toreador`, `ventrue`; available agents:
`random`, `heuristic`):

```sh
uv run python scripts/run_matchups.py --p1-deck brujah --p1-agent heuristic \
    --p2-deck toreador --p2-agent random --games 1000
```

Reports land under `logs/games/<p1_agent>_<p1_deck>_vs_<p2_agent>_<p2_deck>/`
(gitignored — run artifacts, not source).

## Known limitations

- No CLI/UI: games are driven by scripts and test scenarios only.
- Only 46 of the 311 cards on the active 2P allowed list have a dedicated
  effect module; unimplemented cards are excluded from the playable pool
  rather than guessed (CLAUDE.md §2).
- Only a heuristic agent exists beyond random-legal play; no search-based
  agent yet (CLAUDE.md §9, milestone 7).
- Any rule or card interaction not settled by the official sources is
  tracked in [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md) rather
  than guessed.
