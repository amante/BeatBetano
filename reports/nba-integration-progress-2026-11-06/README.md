# NBA integration: actual progress and remaining data work

The daily publisher currently emits Elo baseline probabilities. A successful
publication does not establish that injury, replacement, fatigue or trajectory
features influenced those probabilities. Today's published probabilities are
unchanged by this PR.

This change reuses the existing postmortem engine, without a duplicate model:
- Confirmed, projected and unknown starting lineups are distinguished explicitly.
  Projected or unknown starters no longer block research ML/+20 calculations.
  The full sourced rotation, injury states and statistical inputs are still
  required. No player metrics are invented to fill missing coverage.
- Invalid projected starters (duplicates, foreign players, out players) and
  future/stale lineup evidence remain rejected.
- NBA daily runs write an integration diagnostic tied to the exact baseline hash;
  the multisport status includes matching diagnostics only. Counts of available
  baseline forecasts and integrated research outputs are separate.
- Publication is independent of betting eligibility and validation. Research
  probabilities are not automatically promoted into the published baseline.

## Remaining implementation, in dependency order

1. Automatically collect point-in-time full rosters, injury reports, projected
   rotation and prior game schedule/load for BOTH opponents. Retain source bytes,
   timestamps and uncertain assumptions. Existing possession_player_bridge.py
   expects normalized possession/lineup exports and player-role context; the daily
   workflow currently supplies neither. Raw scoreboards alone cannot provide them.
2. Connect supported historical possessions/player minutes to that bridge to
   estimate player effects, opponent-adjusted turnovers and path features. Coverage
   failures must identify the exact missing source; do not substitute zero effects.
3. Publish a separately identified integrated Challenger track (both ML sides and
   both +20 sides) alongside the baseline, preserving revisions and assumptions.
   Questionable-player branches currently remain unweighted scenarios; they must
   not be described as a probability-weighted forecast.
4. Walk-forward evaluation and calibration before claiming validated improvement.
   The November 5 Orlando/Phoenix and Miami/Golden State outcomes remain observed
   regression evidence, never recovered prospective probability records.

## Validation

357 NBA tests and 53 multisport tests passed. New synthetic integration tests
exercise the existing daily reporting function and complete engine with projected
and unknown starters, two-sided ML/+20 outputs, invalid/future lineup rejection,
and explicit zero integrated output when data are absent. These tests verify
behavior, not predictive accuracy or real-data availability. No live integrated
forecast has been generated or claimed by this change. No odds inputs added.
