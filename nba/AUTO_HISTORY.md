# PR #37 — NBA verified automatic history

The preparation workflow loads three completed regular seasons from the verified
repository archive and updates the current season only through the preceding UTC
day. The prediction workflow consumes that prepared evidence rather than rebuilding
history. Same-day finished games remain excluded to avoid result leakage.

Run **NBA prepare historical evidence** for the target US scoreboard date, then
provide its run ID to **NBA automatic verified-history pregame**. These workflows
are manually triggered; this change does not add scheduling or automatic settlement.
Predictions remain research candidates. ESPN classifications and coverage still
require monitoring. Use sources in accordance with their terms.

## Incremental history (PR #341)

Completed seasons now load from the manifest-verified repository archive:
3,690 games, zero source requests. The three-season PR backtest uses that same
frozen ledger, so routine evaluations no longer redownload entire seasons.
A full historical source refresh is an explicit maintenance operation using
`espn_games.py`, never an automatic fallback when a stored digest fails.

Current-season preparation stores each queried ESPN scoreboard date under
`--workdir/2027/daily`. Repeated runs reuse verified days, including empty days;
only missing dates are requested. With a current store, tomorrow's preparation
requests only the previous day's delta. After missed runs, it fills the missing
interval. An unfinished scoreboard is not frozen; source failures and integrity
mismatches stop processing. Existing records are not silently replaced.

Player and team boxscore collection now accepts `--cache-dir` and reuses
per-game observations with fixture identity and digest checks. Original player
observation times are preserved. Only missing game IDs in the selected historical
window require requests; failed collections remain retryable.

The preparation workflow restores and saves `results/nba/raw` using Actions cache
and includes the store in its 90-day artifact. A cold or evicted cache requires
bootstrapping the current season and selected boxscore windows once; it still
never redownloads the three completed seasons. For longer retention, preserve
the raw store outside expiring Actions storage. Concurrent runs use distinct
cache keys; every restored date and observation is independently verified.
