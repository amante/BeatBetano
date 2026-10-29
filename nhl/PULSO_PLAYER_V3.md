# PULSO PLAYER NHL v3

Extends v2 from one skater to roster-discovered skaters with sourced NHL team **regular-season schedule rest** (not player appearance-gap rest), plus forwards/defense and rest-cohort MAE.

## Use

Run GitHub Actions `PULSO PLAYER — NHL v3 team-rest and multi-player replay`, `Run workflow`, choose `main` and specify `teams=EDM` (default). Output: `metrics.json`, `predictions.json`, `provenance.json`. After reviewing EDM, try more team abbreviations as comma-separated values. `ALL` is supported but requires substantial NHL API fetch traffic; do not imply entire league was tested until a run completes.

Endpoints:
- `/v1/roster/{team}/{season}`: candidate historically rostered skaters (not point-in-time lineup confirmation)
- `/v1/club-schedule-season/{team}/{season}`: dated actual team regular-season games
- `/v1/player/{player}/game-log/{season}/2`: individual logged game outcomes

No odds, no made-up output, no claim of final model calibration. Historical player observations are restricted to dates **before** each prediction, and the actual player roster in a target game is only known retrospectively for research; real pregame roster prediction requires a separate availability feed and frozen snapshot.

No standalone goals-probability model in v3: goal MAE is descriptive only; probabilities need separate count/binary calibration. No claim of performance uplift until manual live-data workflow returns metrics.
