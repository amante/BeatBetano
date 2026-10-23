# BeatBetano NBA — 2026–27 model track

NBA lives alongside NFL within this repository; NFL `validation/` is untouched.

## Official NBA 2026–27 candidate v0.1
- A reproducible, odds-free chronological Elo **benchmark**, not a calibrated official full model.
- Inputs: unique game_id, season (starting year, 2023/2024/2025), `tipoff_utc` (UTC ISO 8601), home_team, away_team, final home_points/away_points. Future games must have scores set to null.
- Features available at tipoff: prior-game team strength and explicit home-court advantage. No player injuries or projected starters included yet.
- DUAL filter: difference of win probabilities <= 6 percentage points, **necessary but not sufficient**.
- P(any team leads by 20) deliberately NOT estimated: requires in-game scoring/maximum-lead historical data, rather than final scores alone.
- To evaluate using three real completed NBA seasons, ingest a properly licensed/authorized source with verified chronological game schedules, team IDs and final scores; report per-year and pooled out-of-sample Brier/log loss and calibration. No results claimed until those backtests complete.
- Separately maintain a Challenger 2026–27.1 using pregame team-player availability, opponent-adjusted net rating and lineup continuity when independently verified and backtested.
- NBA and NFL share only code hosting and CI, not model coefficients, ratings or data.
