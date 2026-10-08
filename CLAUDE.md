# VtES Duel Bot

A bot that plays **Vampire: The Eternal Struggle** in a **two-player duel**. The user supplies a deck; the bot pilots it against a human (or another bot) under the official VEKN two-player variant.

Reliability comes before strength: **a bot that always plays legally and never mis-resolves a card is the first milestone.** Playing well comes second.

---

## 1. Scope

**In scope :**

- The VEKN **two-player variant** [open playtest](https://www.vekn.net/two-player-format)
- Only cards on the official **List of allowed cards in 2-player VTES** (versioned, see §4).
- Deck import + legality check, rules engine, bot decision-making, simulation (bot vs bot), a first CLI interface.

**Out of scope (for now) :**

- 4–5 player multiplayer VtES.
- Cards outside the 2P allowed list.
- Physical-table play (see Open decisions, §8).

---

## 2. Sources of truth — and the no-guessing rule

Precedence, highest first:

1. **Card text** (VEKN official texts). Rulebook "Golden Rule for Cards": *whenever the cards contradict the rules, the cards take precedence.*
2. **Official rulings** for that card (VEKN Card Rulings / General Rulings, also exposed by KRCG).
3. **VEKN two-player variant** page (overrides the rulebook where it says so).
4. **VEKN [Rulebook](https://www.vekn.net/rulebook) v1.1 (October 2023)**

**Never invent, extrapolate or "fill in" a rule or a ruling.** If a situation is not covered by the sources above, or the sources conflict:

- do **not** pick an interpretation silently;
- add an entry to `docs/OPEN_QUESTIONS.md` (situation, sources consulted, candidate readings);
- make the engine raise `UnresolvedRulingError` (or exclude the card from the playable pool) until the question is settled by the user.

Every rule implemented in code cites its source in the docstring (e.g. `Rulebook §4 Minion Phase > Detailed course of an action` or `2P variant §2.3 Starting transfers`).

---

## 3. Two-player variant — deltas from the rulebook

All rulebook rules apply **except** (source: VEKN 2P variant page, Ginés Quiñonero, modified 2025-05-20, plus updates page):

| Topic | 2P rule |
| ----- | ------- |
| Players | 2 (instead of 4–5) |
| Library size | 40–60 cards (instead of 60–90) |
| Crypt | rulebook: at least 12 cards, one group or two consecutive groups |
| Allowed cards | only the 2P allowed list |
| Contested crypt cards | a contested crypt card **stays in play and usable**; contest costs 1 pool each unlock phase or yield (burn) |
| Contested titles | if two copies of the same vampire both have a title, the title is **not** contested |
| Starting transfers | first player gets **3** transfers on their first influence phase; then 4 for everyone |
| Time limit (optional) | 30 minutes suggested |

Structural consequence (rulebook, §5 Ending the Game): with two Methuselahs left, **each is the other's prey (and predator)**. Undirected actions can be blocked by prey or predator → in a duel the opponent can attempt to block essentially every action. Any card whose text distinguishes prey from predator must be checked against this; if the outcome is unclear → Open Question.

The format is a **living playtest** (cards are added/removed; last observed update: 2026-10-03). Never hard-code legality.

---

## 4. Data

- Card texts and rulings: **KRCG** (`pip install krcg`, Python library by Lionel Panhaleux; also an online API). Verify the API against the installed version before relying on it.
- 2P allowed list: stored as `data/formats/2p/<YYYY-MM-DD>.json` (one file per VEKN update) + `data/formats/2p/CHANGELOG.md`. The active version is selected by config, never implicit.
- Suggested 2P decklists from VEKN: stored in `data/decks/vekn-2p/` as regression fixtures.

---

## 5. Architecture

```text
src/vtesbot/
  engine/        # pure rules engine: state, phases, impulse/sequencing, actions, blocks, combat, politics, torpor/diablerie
  cards/         # one effect module per card + registry; cards register hooks, they never patch the engine
  formats/       # legality checks (2P variant), allowed-list loading
  decks/         # deck parsing & validation
  agents/        # Player interface + implementations (random legal, heuristic, search-based)
  sim/           # bot-vs-bot runner, replay logs
  interface/     # CLI (first), later TBD
data/
docs/
  OPEN_QUESTIONS.md
  DECISIONS.md   # architecture decision records
tests/
  rules/         # scenario tests from rulebook examples
  cards/         # one test file per implemented card
  sim/           # smoke & stability tests
```

**Engine invariants:**

- **Deterministic**: all randomness through a seeded RNG owned by the game state. Same seed + same decisions ⇒ same game.
- **Pure core**: no I/O, no printing, no network in `engine/` and `cards/`.
- **Decision points are explicit**: whenever any player may act (impulse, block attempt, combat steps, votes, out-of-turn masters), the engine yields a `Decision` with the full list of **legal choices**. Agents only ever pick from that list. This is what guarantees legal play.
- **Information hiding**: agents receive an `Observation` (own hand, public zones, counts of hidden zones), never the raw `GameState`. A bot must not read the opponent's hand, library order or face-down uncontrolled vampires.
- **The impulse model is first-class**: acting Methuselah first; after any effect, impulse returns to the acting Methuselah (Rulebook §2 Sequencing). The bot acts during the **opponent's** turn too.
- **Full replay log**: every decision and every random draw is logged so a game can be replayed and a bug reproduced.

---

## 6. Conventions

- Python ≥ 3.14, full type hints, `dataclasses` or `pydantic` for state.
- Tests: `pytest`. Lint/format: `ruff`. (Adjust here once the tooling is settled.)
- A card is **implemented** only when: effect code + test(s) covering its text and each known ruling + registry entry + listed in the active 2P list.
- A rule is **implemented** only when a scenario test exists, ideally reproducing a worked example from the rulebook.
- Commits are small; one card or one rule mechanism per change.

---

## 7. Agents and skills

| Kind | Name | Use it for |
| ---- | ---- | ---------- |
| agent | `rules-engineer` | engine mechanics: phases, impulse, actions, blocks, combat, politics, torpor |
| agent | `card-implementer` | turning a card's official text + rulings into an effect module with tests |
| agent | `rules-auditor` | independent read-only review of rules/card code against the sources |
| agent | `test-engineer` | scenario tests, ruling regression tests, bot-vs-bot simulations |
| agent | `bot-strategist` | the decision-making agents (heuristic, then search under hidden information) |
| agent | `format-curator` | syncing the VEKN 2P allowed list, decklists and changelog |
| skill | `vtes-rules-reference` | condensed rules with section pointers + the no-guessing procedure |
| skill | `implement-card` | step-by-step workflow for one card |
| skill | `sync-2p-format` | updating the allowed list from VEKN |
| skill | `rules-scenario-test` | how to write an engine scenario test |
| skill | `deck-validation` | parsing a decklist and checking 2P legality |

High-stakes changes (core engine, combat, impulse) are reviewed by `rules-auditor`, which has not written the code.

---

## 8. Open decisions (do not decide silently — ask the user)

- **Interface**: digital (engine knows the full state) vs physical table (user transcribes every action and answers every impulse prompt). Default assumption until decided: **digital, CLI first**.
- **Bot strength target**: "always legal" (milestone 1) → "reasonable" → "strong". Approach for the strong bot (heuristics, determinized MCTS / ISMCTS, RL) is not settled; no published VtES benchmark is known to the project.
- **Frontend** beyond CLI: not decided.

---

## 9. Milestones

1. Deck import + 2P legality check.
2. Engine skeleton: setup, turn phases, influence/transfers (2P), bleed/hunt, block attempts, basic combat (hand strikes), ousting/victory.
3. Card pool for **2–3 VEKN suggested decks**, fully tested.
4. Random-legal agent; 1,000 seeded bot-vs-bot games without crash or stuck state.
5. Heuristic agent.
6. Full 2P allowed list.
7. Search-based agent.
