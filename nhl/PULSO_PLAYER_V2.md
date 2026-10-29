# PULSO PLAYER v2 — first sourced player replay

The NHL Web API game-log endpoint is used for skaters. Each row includes a source-recorded game, player ID, date, opponent, site, minutes, SOG and goals. All projections use game dates **strictly earlier** than the target date.

The provider endpoint is `https://api-web.nhle.com/v1/player/{player}/game-log/{season}/2`.

Source: NHL public statistics. No market odds. Fail closed on malformed data.

`nhl/data/player_ids_seed.json` starts deliberately with one known skater (Connor McDavid, player ID 8478402) to validate real ingestion. Expand to an independently verified league-wide player-ID roster before making multi-team claims. The regular season files cover 2023-24 through current 2026-27; availability and incomplete 2026-27 seasons are disclosed.

On GitHub, use **Actions → PULSO PLAYER — NHL sourced historical replay v2 → Run workflow**. The artifacts include CSV, source manifest and replay scores (MAE for TOI/SOG/goals). Unit tests on PR do **not** imply data was downloaded. Full ingestion runs only on manual dispatch, so missing access is visible.

Caveats: first appearance lacks exact prior-game rest; these rows are skipped. Player's time since last *appearance* is not the same as team back-to-back, and will require correction for missed games. The initial v1 contextual model uses player prior games, opponent identity and home/away; injury, lineup, role and goalies are not yet available. No validated multi-player or team ML prediction until samples and controls are expanded.
