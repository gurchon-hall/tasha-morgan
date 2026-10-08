---
name: rules-scenario-test
description: How to write deterministic scenario tests for the VtES rules engine and cards — building a precise game state, scripting decisions, asserting outcomes and citing the rule source. Use when writing or reviewing tests under tests/rules or tests/cards.
---

# Writing a rules scenario test

## Principles
- **Expected values come from the sources**, never from running the code and copying its output.
- One scenario = one rule or one card clause. Name it after what it proves.
- Fully deterministic: fixed seed, explicit library order when draws matter.
- Cite the source in the test docstring (rulebook section, 2P variant section, card ruling).

## Shape
```python
def test_aggravated_damage_burns_wounded_vampire():
    """Rulebook §4 Damage Resolution — aggravated damage on a wounded vampire.
    Worked example: a ready vampire with 1 blood takes 2 normal + 1 aggravated
    damage; burns 1 blood to mend, is wounded by the 2nd point, and the
    aggravated point burns him."""
    game = ScenarioBuilder(seed=1, format="2p") \
        .player("A").ready_vampire("V1", capacity=3, blood=1) \
        .player("B") \
        .build()

    game.apply_damage(target="V1", normal=2, aggravated=1, source=None)
    game.run_until_decision_or_end()

    assert game.zone_of("V1") == "ash_heap"
```
(`ScenarioBuilder` and helper names are the project's test helpers; create them in `tests/helpers.py` if absent and keep them in sync with the engine API.)

## Scripting decisions
Use a `ScriptedAgent` that answers decisions from a list and **fails the test** if:
- the engine asks a decision the script did not expect;
- a scripted choice is not among `decision.choices` (proves illegal options are not offered);
- the script still has unused answers at the end.

Always also assert what was **offered**: e.g. that a stealth modifier is *not* offered when no block attempt is ongoing.

## Checklist for an engine mechanism
- happy path;
- each branch named in the source (e.g. block succeeds / fails / declined; combat ends early);
- the "only when needed" constraints (stealth, intercept);
- 2P variant behaviour, and the rulebook behaviour when the 2P format is off, if both exist;
- invariants after the step (no negative counters, card conservation, hand size).

## Rulebook worked examples worth reproducing first
Influence phase (Nora / Alexa Draper transfers), combat with additional strikes (Wauneka / Flávio Gonçalves), steal blood vs ally (Chrysanthemum / Underbridge Stray), aggravated damage (Nassir, Tamoszius, Ryan), bleed with Bonding after blocks declined (Sully / Alexis), block with reaction card on a hunt (Wauneka / Ayelech).
Note: some cards named in these examples may not be in the 2P allowed list; use them only as rules fixtures, built directly with the builder, not as playable cards.
