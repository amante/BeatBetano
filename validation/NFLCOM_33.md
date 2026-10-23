# NFL.com 3.3 game and team evidence gate

NFL.com 3.2 retrieved and parsed **15 real rows** from a weekly league injury page, but those rows currently lack verified team and match context. This module joins an independently reviewed row-to-team/game mapping with a kickoff schedule. Rows outside the paired teams or captured after kickoff are rejected. An unresolved record is not assigned a team on the basis of player name.

Important: assignment inputs must be explicitly reviewed against the original NFL.com page's team groupings (or corroborating league/game report), NOT invented from the player's current team. Source rows with identical player/position/status require stable row IDs in a later parser version; the current code refuses duplicate assignment keys. GSIS identity remains an additional independent verification gate. No win-probability or player-prop coefficients are modified.

Inputs:
- parsed rows: source_url, captured_at_utc, player_name, position, game_status
- assignments: source_url, player_name, position, game_status, team, game_id
- schedule: game_id, home_team, away_team, kickoff_utc

Usage:
```
python validation/nflcom_game_context.py --rows ROWS.csv --assignments REVIEWED_CONTEXT.csv --schedule GAMES.csv --output results/nflcom_context
```
No full-season 2026 NFL.com feed has been implemented by this PR.
