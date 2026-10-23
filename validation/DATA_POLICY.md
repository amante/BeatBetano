# Data provenance and promotion protocol

## Dataset contract
NFL: `home_team,away_team,home_score,away_score,season,gameday` with optionally `week,game_type`.
NBA play-by-play: `game_id,home_score,away_score` after scoring events. Real datasets may require a documented mapping. Verify score updates are chronological and games are complete.

## Temporal integrity
1. Record data snapshot time, provider, source URL, season, licensing and extraction date.
2. Do not incorporate post-game results into pre-game features.
3. Keep immutable pregame forecasts for official and challenger models with model_version, game_id, forecast_timestamp and data_cutoff.
4. Compare on the SAME out-of-sample games with proper scoring rules (Brier/log loss), reliability plots and uncertainty intervals.
5. Record missing games, ties, cancellations, postponed matches and missing lineups.
6. Separate calibration fit period from evaluation; no calibrating on the test split.
7. Never anchor sports projections on betting odds.

## Scope boundaries
The present NFL Elo algorithm is a baseline only. It is not the user's official NFL 2026–27 model.
The NBA 20-point engine currently extracts observed historical events only. It does not estimate pregame probability.
The synthetic tests assert code semantics, not empirical predictive validity.
