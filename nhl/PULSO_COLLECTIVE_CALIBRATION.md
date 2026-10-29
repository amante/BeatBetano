# NHL collective chronological calibration — outcome baseline

This stage establishes per-target hyperparameter tuning on **2025-10-01 through 2026-02-28** and frozen chronological evaluation **from 2026-03-01 onward**, independently for ML, regulation (home/draw/away), first-to-3-goal lead and each team's probability of reaching +3.

All features are strictly previous-date historical outcomes; probabilities do **not** use market odds. The methods are baseline frequencies and shrunk prior team-role outcomes. Metrics: Brier and log loss versus global historical baseline, including year segment.

Historical labels do **not** contain historically captured pregame projected lineups, goalie confirmations, CRS ratings or player-v5 predictions. Training with those as if they were sourced pregame would leak information. This PR explicitly reports missing coverage and does **not** claim an integrated player-enhanced model. The player-to-team bridge in PR #205 is an operational feature contract, not a retroactively available training set.

To use with the existing archive (after locating actual file): `python -m nhl.pulso_collective_calibration --labels PATH_TO_OFFICIAL_LABELS.csv --out results/nhl/pulso_collective_calibration.json`.

After CI, run this with authentic historical label dataset and inspect per-target holdout improvements; then build a **prospective frozen feature ledger** of player, goalie, roster, unit and PP/PK observations and evaluate on subsequent completed games. No automatic production promotion.
