# NBA: 2023–24 through 2025–26 backtest, official-model baseline stage

An optional GitHub Actions workflow manually fetches the three completed regular seasons from public ESPN scoreboard requests. It rejects missing or duplicated fixtures, demands 1,230 games for each standard NBA regular season, and scores Elo predictions made before incorporating each game's final outcome.

**Warm-up**: season ending 2024. **Out of sample**: season ending 2025 and season ending 2026. It prints Brier and log loss separately for each holdout and their pooled result. It does NOT assert that Elo is calibrated or better than any alternative. No NBA advanced player features are fitted yet: licensed and point-in-time inputs are still pending.

If the source changes, blocks requests or labels season fields differently, the workflow fails with an explicit problem rather than fabricating data. Daily ESPN scoreboard snapshots are requested for historical completed games; ingestion date is not the original publication timestamp.

To run: GitHub Actions > NBA three-season chronological backtest > Run workflow on the branch containing the workflow. Inspect the resulting artifact before using reported numbers.

The official 2026–27 production model is NOT yet ready: after this phase we must verify dataset provenance, calibration, lineups and injury data, and the 20-point-lead feature. NFL remains untouched.
