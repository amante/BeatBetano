# PULSO NHL player-to-team bridge — pregame feature contract

Joins prospective, timestamped NHL fixture identities with eligible v7 player forecasts and already linked ESPN-to-official-NHL goalie identities from the v204 crosswalk.

The output provides **descriptive sums** of skater expected ice time, shots and goals by team, coverage counts, and goalie identity readiness. These quantities are NOT NHL team goal rates, and no untrained weights are silently added. The goalies are independently linked as identities but **not independently confirmed as starters**.

CLI:

`python -m nhl.pulso_team_bridge --fixture fixture.json --players v7-player-predictions.json --goalies goalie_identity_crosswalk.json --out team-features.json`

All 12+ skaters per team must have same-fixture, pre-start eligible projections. Missing or post-start evidence fails closed. No output is scored or published as an official prediction. Goal process v8 is intentionally **not** called by this bridge.

## Validation/promotion still required

1. Source-backed game-specific expected player availability and injury status. Current official rosters are only candidates. The historical v5 player model still needs current-game feature adaptation and rest.
2. Confirm goalies via actual source assertion + independent evidence, as-of puck drop.
3. Fit collective goal-rate model using strictly earlier historical team games and *historical as-of player projections*, check Brier/log loss and calibration across walk-forward holdouts; compare to goal-process and historical-target baselines.
4. Freeze prospective run evidence, measure outcomes and only then consider official ML/RT/+3 promotion.

This PR delivers the feature integration boundary and tests, not a trained model.
