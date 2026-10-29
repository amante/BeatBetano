# PULSO research-to-pregame boundary (v6/v7)

## What this PR provides

- A conservative, explicit temporal auditing utility: each actual pregame source must carry its source timestamp and fixture cutoff. Retrospective dated game logs **do not prove** pregame publication.
- An independently supplied, HTTPS-sourced, timestamped roster snapshot is REQUIRED; missing or after-puck-drop snapshot is rejected.
- Player identity, fixture-side, and statuses (confirmed, probable, questionable, out, unknown) have explicit source-availability treatment. Only confirmed/probable candidates are projected, while ambiguous/out players are reported as exclusions, **not assumed to start**.
- All target player projections use the v1 strictly-before-game-date historical forecast. Unknown rest is an error, not a guessed default.
- An incomplete roster fails the full-team gate and the output remains `research_only_no_collective_ml`; this PR does not claim NHL team-game predictions.

## Remaining pregame feed work

This PR is a **snapshot contract and gate**, not an automatic roster/goalie feed. A real trusted pregame provider must be wired to collect as-of statuses, roster completeness, confirmed/probable goalie, and fixture schedule. Feed retrieval, historical proof of availability and prospective shadow tracking must be validated before production predictions.

## CLI

`python -m nhl.pulso_pregame_v7 --snapshot snapshot.json --logs player_logs.csv --rest rest.json --game-start-utc 2026-10-30T00:00:00Z --out out.json`

The external snapshot JSON must include `asof_utc`, `source_url`, `game_id`, `home_team`, `away_team`, and `players` with `player_id`, `team`, `status`. This does **not** accept retrospective played-game rosters as an alternative.

## Important v6 audit caveat

Historical v5 evaluation used strictly preceding player game logs and frozen historical season parameters; however retrospective roster participation and source retrieval were not captured point-in-time. Consequently leakage risk is NOT fully closed. This module audits actual temporal source metadata prospectively when available, without pretending prior v5 snapshots exist.
