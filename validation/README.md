# Sports Model Validation — MVP

Isolated, odds-free historical evaluation for the five sports (NFL/NBA first). This folder does **not** change the React app, production recommendations, or model parameters.

## Run

Python 3.10+ and pandas, numpy, requests.

```bash
pip install -r validation/requirements.txt
python validation/backtest.py fetch-nfl --output data/nfl_games.csv
python validation/backtest.py nfl --input data/nfl_games.csv --output results/nfl
python validation/backtest.py nba-20 --input data/nba_play_by_play.csv --output results/nba
```

NFL input: nflverse `nfldata/data/games.csv`, fields `home_team,away_team,home_score,away_score,season,gameday` (and optionally `week,game_type`). Baseline: pregame Elo, predictions recorded before postgame rating updates, season regression, held-out last two seasons. NFL ties are excluded and counted. Some games on the same date may be processed as a batch; this is a simple benchmark, **not** the user's official 2026–27 model.

NBA input: play-by-play rows with `game_id,home_score,away_score` after each scoring play (common aliases accepted). Detects whether either team **ever** led by 20+ points, not final margin. This produces observed events/frequency, **not** a pregame forecast.

## Safeguards
- Sports-only predictions. **No bookmaker odds/market inputs**.
- Outputs report sample size and test seasons. Do not describe reconstructed Elo as the user's official model.
- Test observations must follow training observations chronologically; no postgame features.
- Do not upgrade experimental challenger 2026–27.1 without separate blind holdout results, calibration curves, Brier and log loss.
- No claims of backtests until data actually processed.
- Do not commit scraped personal or licensed datasets to this repository.

Next: import actual frozen official predictions, NBA calibrated predictor, joint NFL props, and adapters for football, NHL and tennis.
