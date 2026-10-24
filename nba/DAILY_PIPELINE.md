# NBA PR #36 — current scoreboard + three-model execution

Use **NBA verified pregame three-model run** from GitHub Actions with two inputs:
- `game_date`: league scoreboard date, YYYY-MM-DD;
- `history_file`: a repository JSON file of verified completed NBA regular-season games through the current time. Include cleaned 2023–24 through 2025–26 baseline history AND all completed 2026–27 regular-season games. Do not include NBA Cup final / All-Star contamination.

The job fetches today's ESPN scoreboard, rejects started games, then generates immutable predictions for all upcoming fixtures in the selected date: Elo, Challenger and experimental hybrid. The snapshot is timestamped and archived as a per-run artifact for 90 days. **No source history file is automatically populated, and no scheduled run exists yet.** If data is missing, stale, or a game already started, execution fails; do not claim a prediction.

All probabilities are provisional and do not incorporate verified starting lineups, injuries, or advanced efficiency. This workflow is an integration step toward automation, not an unattended forecasting service. Model candidate tags and bet eligibility flags remain unchanged.
