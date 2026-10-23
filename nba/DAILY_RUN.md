# NBA daily prediction runner

Given a separately verified historical regular-season JSON and the day's verified official fixtures, this module prints Elo benchmark probabilities without any sportsbook odds.

```
python nba/daily_predictions.py --history HISTORY.json --fixtures OFFICIAL_GAMES.json --date 2026-10-23 --output results/nba/daily_predictions.json
```

**Important limitations:** This runner does not download today's official fixtures itself, does not backtest/calibrate the model, and does not include injuries, starters, player efficiency, the 20-point lead market or economically viable DUAL tickets. Date is interpreted as **UTC**, not local; the future web UI must convert user/local league calendar days to explicit UTC ranges before generating fixture inputs. It prevents historical outcomes after the requested day's UTC midnight from entering Elo and refuses final scores inside prediction fixtures.

For a complete production system, wire an authorized official schedule feed and point-in-time player availability snapshots, and evaluate on proper chronological holdouts first.

PR #24 historical three-season backtest must be run separately; passing test suites is not evidence of predictive calibration.
