# NBA prospective tracking — PR #34

The predictor provides a **prospective comparison harness**, not a ready-to-use automated NBA forecast service. No betting odds enter the model.

## Inputs and process

Provide a verified completed-game JSON history **up to the moment of snapshot creation**, containing each game's ID, season end-year, UTC tipoff, teams and completed points; and a separate future-fixture JSON with null scores. Each prediction snapshot includes three frozen pregame probabilities: Elo, Challenger and experimental hybrid.

`python nba/prospective.py --history verified_history.json --fixtures future_fixtures.json --timestamp 2026-10-23T22:00:00Z --snapshot snapshot.json`

`python nba/prospective.py --snapshot snapshot.json --results verified_results.json --report settlement.json`

GitHub Actions > **NBA prospective snapshots** can generate a per-run archived snapshot after validated input files have been added to the repository. It captures the UTC timestamp when the job runs; if a game has already started it fails rather than recording post-tipoff probabilities as pregame. It will never replace an existing snapshot file in the local run, and GitHub archives snapshots as per-run artifacts.

**Not yet implemented**: scheduled automated daily source refresh, importing ESPN current-season game/fixture snapshots, permanently persisted snapshots beyond artifact retention, automatic result settlement, actual starter/injury validation, advanced efficiency metrics, calibration, 20-point-lead probability, or the user-facing web dashboard. GitHub archives have 90-day retention; move snapshots to durable versioned storage before claiming permanent provenance. The fixture feed and result snapshot must remain independently verifiable.

The hybrid is post-hoc, not independently validated. `eligible_for_bet=false` on every snapshot, including DUAL candidates; do not infer profitability.

**Important time-zone caveat**: UTC tipoff timestamps are used for cutoff and comparison. A US/Chile local NBA game date can span two UTC dates and must be handled by the upstream fixture importer.
