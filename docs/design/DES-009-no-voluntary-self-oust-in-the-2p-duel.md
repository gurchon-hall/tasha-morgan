---
status: resolved
date: 2026-10-13
cards:
---

# DES-009 - No voluntary self-oust in the 2P duel

- Context: the engine offered choices that ousted their own chooser:
  spending the last pool on an influence transfer (1 transfer, or 4
  transfers + 1 pool, at 1 pool), burning the whole pool for votes
  (Oxford University, England), and every other self-paid pool cost
  (contest payments, Wider View's play cost, Kine Resources Contested's
  self share). Some effects also make a Methuselah lose pool with no
  choice at the moment of loss (Fame's torpor burn of 3 and unlock-phase
  burn of 1, Marcos Belegrad's burn for those who voted against). The
  rulebook's Influence Phase "Nora" example says she "cannot use both
  counters in her pool to put that vampire into play because that would
  put her out of the game"; no rulebook or card-ruling source covers the
  general case.
- Decision: user rulings (not derived from the rulebook): "à 2 joueurs,
  tu peux tomber à 0 pools à cause de tes actions mais l'objectif étant
  de gagner, on va dire que cela est interdit quelle que soit la
  manière de perdre du pool", and "auto-oust impossible à 2 et 3
  joueurs, possible à 4 et 5 joueurs" (an earlier wording, "c'est un cas
  réservé aux parties à 3+p, bloquer dans le format 2p", is superseded by
  it). A Methuselah never gets an option that would bring their own pool
  to 0 by their own choice. Losses caused by the opponent still oust.
  Addendum (user ruling 2026-10-13: "fame continue de fonctionner
  normalement car aucun choix n'est fait une fois fame en jeu. les choix
  qui mène l'agent lui même à 0 sont interdits"): forced effects with no
  choice at resolution (Fame) still oust normally; any choice whose
  consequence, even downstream, would take the chooser to 0 is not
  offered.
- Consequence: `engine/pool.py::can_afford_without_ousting` /
  `max_voluntary_spend` are the single gate for every voluntary option:
  influence transfers (`engine/phases/influence.py::_available_choices`
  offers `add_blood`/`bring_crypt` only at pool >= 2; hook-offered
  influence options such as Wider View spend no pool), burn-for-votes
  (X <= pool - 1, minus `pending["pool_reserve"]`), the four contest
  pay-or-yield decisions (only yield remains), Wider View's play, and
  Kine Resources Contested (own share <= pool - 1, reserved during its
  referendum; see RUL-013). A vote against a Marcos Belegrad referendum
  is withheld when `pool - 1 - reserve < 1`, via
  `politics.VOTE_AGAINST_POOL_COST_HOOK` (checked at casting, burned at
  tally). A deliberate simplification of the 2P duel, to be revisited if
  4-5 player games are ever in scope.
