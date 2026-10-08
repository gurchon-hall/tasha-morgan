---
name: deck-validation
description: Parses a VtES decklist (crypt + library) and checks its legality for the two-player variant, reporting every violation with its source. Use when the user supplies a deck, when importing VEKN suggested decklists, or when building the deck loader.
---

# Deck parsing and 2P validation

## Input
Accept plain-text decklists with a crypt section and a library section, lines like `2x Card Name` or `2 Card Name`. Do not assume one site's export format; if a line cannot be parsed, report it with its line number instead of skipping it.

## Name resolution
Resolve every name through KRCG (`VTES[...]`, `VTES.complete(...)` for suggestions). Ambiguous or unknown names are reported with the suggestions; never auto-pick.

## Checks (each violation cites its rule)
| Check | Rule | Source |
|---|---|---|
| Crypt size ≥ 12 | no maximum | Rulebook §1 Deck construction |
| Crypt groups: one group or two consecutive | ANY-group cards per their text | Rulebook §1–2 Deck construction |
| Library size 40–60 | replaces 60–90 | 2P variant §2.3 |
| Every card on the active 2P allowed list | crypt and library | 2P variant §2.3 + `data/formats/2p/<date>.json` |
| Card types correct per section | a vampire in the library section is an error | Rulebook §1 |
| Implementation status | informational: cards `blocked` or not yet implemented | project registry |

Note: the rulebook places no limit on copies; do not invent one.

Run the checks with `scripts/validate_deck.py` (not a one-off inline script —
keeps the checks reproducible across decks and syncs):
```
python scripts/validate_deck.py <deck.json> --format data/formats/2p/<date>.json
```
It covers crypt size/groups, library size, and allowed-list membership + type
per section; it does not check "Implementation status" (that comes from the
project's card registry, which doesn't exist yet) — report that part by hand.
Any name left in the deck fixture's own `"unmatched"` array (from
`scripts/krcg_match.py`) is reported as a violation, never guessed.

## Output
```
Deck: <name>   Format: 2p @ <list date>
Crypt: <n> cards, groups {..}   Library: <n> cards
LEGAL | ILLEGAL
Violations:
 - <rule>: <detail>  (source)
Not yet playable by the bot:
 - <card>: blocked (OQ-n) | not implemented
```
A deck can be legal yet not playable by the bot; keep the two verdicts separate.
