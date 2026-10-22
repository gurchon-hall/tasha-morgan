---
name: rules-scenario-test
description: >-
  How to write deterministic scenario tests for the VtES rules engine
  and cards — building a precise game state, scripting decisions,
  asserting outcomes and citing the rule source. Use when writing or
  reviewing tests under tests/rules or tests/cards.
---

# Writing a rules scenario test

## Principles

- **Expected values come from the sources**, never from running the
  code and copying its output.
- One scenario = one rule or one card clause. Name it after what it
  proves.
- Fully deterministic: fixed seed, explicit library order when draws
  matter.
- Docstring: the source (rulebook section, 2P variant section, card
  ruling) and what it proves, 3 lines max (CLAUDE.md §6).

## Shape

Adapted from `tests/rules/test_damage.py`:

```python
def test_aggravated_damage_on_a_healthy_vampire_wounds_and_torpors_at_once():
    """Rulebook worked example (Nassir): 1 aggravated damage on a ready
    vampire with 1 blood cannot be mended; it goes to torpor, blood kept."""
    game = (
        ScenarioBuilder(seed=1, format="2p")
        .player("A")
        .ready_vampire("V1", capacity=3, blood=1)
        .player("B")
        .build()
    )
    game.state.agents["A"] = ScriptedAgent("A")  # no decision expected

    game.apply_damage(target="V1", aggravated=1)

    assert game.zone_of("V1") == "torpor"
    assert game.blood_of("V1") == 1
```

The helpers live in `tests/helpers.py`: `ScenarioBuilder` (players,
`ready_vampire` / `torpid_vampire` / `uncontrolled_vampire`,
`hand_card(s)`, `library_cards`, `crypt_deck_cards`, `edge_holder`),
`ScenarioGame` (`state`, `vampire`, `zone_of`, `blood_of`, `pool_of`,
`apply_damage`) and `ScriptedAgent`. Read the file before using a
helper; add one there (not in a test) when a scenario needs it, and
keep it in sync with the engine API. Zone names are the engine's own
(`"ready"`, `"torpor"`, `"burned"`, ...).

## Scripting decisions

`ScriptedAgent(player).expect(kind, value)` answers decisions in
order and fails the test if:

- the engine asks a decision the script did not expect;
- a scripted choice is not among `decision.choices` (proves illegal
  options are not offered);
- answers remain unused — only when you call `assert_exhausted()`,
  so call it at the end of any scripted scenario.

Always also assert what was **offered**: e.g. that a stealth modifier
is *not* offered when no block attempt is ongoing.

## Checklist for an engine mechanism

- happy path;
- each branch named in the source (e.g. block succeeds / fails /
  declined; combat ends early);
- the "only when needed" constraints (stealth, intercept);
- 2P variant behaviour, and the rulebook behaviour when the 2P format
  is off, if both exist;
- invariants after the step (no negative counters, card conservation,
  hand size).

## Rulebook worked examples worth reproducing

Influence phase (Nora / Alexa Draper transfers), combat with
additional strikes (Wauneka / Flávio Gonçalves), steal blood vs ally
(Chrysanthemum / Underbridge Stray), aggravated damage (Nassir,
Tamoszius, Ryan), bleed with Bonding after blocks declined (Sully /
Alexis), block with reaction card on a hunt (Wauneka / Ayelech).
Check `tests/rules/` first; some already exist.

Some cards named in these examples may not be in the 2P allowed list;
use them only as rules fixtures, built directly with the builder, not
as playable cards.
