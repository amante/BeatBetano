# NBA real-game data plan

Use three completed regular seasons: 2023–24, 2024–25, 2025–26. The
existing nba/model.py is a reproducible odds-free Elo benchmark candidate.
This PR adds public ESPN scoreboard **ingestion only**, with a short live
network smoke in CI. It is not a validated full-season dataset.

ESPN season.year may be labelled by its ending year; convert source-year
labels explicitly when aggregating by NBA starting season. Never mistake
preseason/postseason for regular season. Cross-check full seasons' game counts
(typically 1,230 regular-season games per 30-team season; exceptions possible),
unique game IDs and date coverage before training. Schedule and team names
must have consistent IDs. Preserve results in GitHub Actions artifacts rather
than committing third-party raw data. Check source terms before deployment.

For chronological backtests, training must precede each evaluation season.
No injury status, lineup, market prices or play-by-play 20-point-lead
information is fetched here. Do not claim NFL/NBA model integration beyond
sharing the same repository and independent CI.
