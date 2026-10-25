# NBA per-game source intake

This workflow now makes separate ESPN game-summary requests for future fixtures, recording the API URL, observation time, and source-specific injury indications. It does **not** mark starting lineups, bench minutes or player-to-player matchups confirmed: ESPN's summary is not authoritative confirmation of those pregame fields. If the summary is unavailable, the runner archives the baseline and its incomplete roster/status diagnostics rather than fabricating a lineup.

Official NBA injury reports are continuously updated and must be separately reconciled: https://official.nba.com/nba-injury-report-2026-27-season/ . Their presence alone cannot be treated as confirmed starting lineups.

Next: parse the official PDF as-of timestamp, reconcile statuses by player/team against the fixture, and link real verified starting lineups to an auditable evidence file; calibrate the resulting availability impact on a distinct holdout set. Until then, integrated win probability is **null**. Do not use sportsbook odds. NFL untouched.
