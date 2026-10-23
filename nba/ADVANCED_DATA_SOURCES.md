# NBA advanced metrics integration — phase 1

Candidate primary: https://www.nba.com/stats/players/advanced
Complement: https://www.basketball-reference.com/leagues/NBA_2026_advanced.html
Prior years: NBA_2025_advanced.html, NBA_2024_advanced.html.

Browser-readable pages do not guarantee lawful or reliable automated access.
Do not bypass robots restrictions, access control or anti-bot systems.
This PR provides a schema and feature gate for a **separately obtained,
authorized** dataset; no live automated data extraction is claimed.

Expected season-end year and team/player identifiers must be cross-walked
to the schedule provider. Basketball-Reference advanced season tables may
contain split team rows and combined TOT rows; reject unresolved duplicates
before allocating player value to any team's pregame lineup. Preserve source
name, timestamp and licensing status in ingestion audit in a future revision.

Never join a final 2025–26 season statistic to an October 2025 tipoff.
For 2025–26 evaluation use complete 2024–25 or earlier stats, or genuine
dated rolling statistics from before the given tipoff. Historical PER, BPM,
VORP, Win Shares are performance signals, not causal estimates of losing a
starter. No automatic availability/ML adjustment is approved yet.
