# NBA pregame module connection

The daily run now emits one post-capture, pregame snapshot and a hash-linked
supporting-module context. A game that has started during capture is omitted.
For every remaining game, the reissued Elo, challenger, and hybrid probabilities
must exactly match the seed snapshot within floating-point tolerance; a failed
comparison stops the run.

The per-game context is carried through `integrated_model.json`,
`nba_hoy.json`, `nba_preliminary.json`, and PULSO's
`nba-predictions-latest.json` as `supporting_modules`.

## Lifecycle meaning

- **Created** means an executable module exists.
- **Connected** means its current per-game output reaches the daily model/PULSO
  payload, including an explicit unavailable or blocked status when evidence is
  missing.
- **Affects prediction** means it changes a forecast percentage. These modules
  remain **No** for this PR. No module field is fed into the probability
  calculation.

The connected context includes:
- player/position crosswalks for reported lineups, without inventing defensive
  assignments;
- historical rotation, joint-minutes allocation, and availability branches;
- conditional production-loss/replacement scenarios and strict feature
  readiness;
- arena-to-arena great-circle distance, destination time zone, UTC-offset
  change, and tipoff-to-tipoff interval.

## Limits and provenance

Roster membership is not game availability. Projected lineups are not confirmed
lineups. Unknown injury statuses stay unknown. Conditional injury production
scenarios do not imply a calibrated win-probability change. Travel distances
are approximate and tipoff gaps are not exact rest because game end times and
flight routes are unavailable.

The workflow accepts an optional direct PDF URL hosted by
`ak-static.cms.nba.com` when the official index is inaccessible. This is a
fallback for a manually known official report URL; it does not fix automated
index discovery or guarantee that the PDF contains player-level statuses.
