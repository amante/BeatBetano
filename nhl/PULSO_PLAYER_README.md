# PULSO PLAYER — NHL research v1

Player-level pregame projections, **not a working official game-odds engine**.

Input: historical **skater** game log CSV with columns:
`game_id,date,player_id,team,opponent,home,rest_days,toi_minutes,shots_on_goal,goals`.

Important: supply independent, source-verifiable historical player logs;
the existing 2,811-game results CSV does **not** contain those player histories.
Do not manufacture shots, minutes or goals. Use `home=true|false`;
`rest_days` is the number of full days since the player's last game (and must
be known before puck drop). Dates in ISO 8601.

Command (once legitimate source data is present):

```bash
python -m nhl.pulso_player_v1 --logs /path/to/player_game_logs.csv --output /tmp/pulso-player-results.json --start 2025-10-01
```

Output scores compare contextual estimates against **the same player's
expanding prior average** on exactly the same pregame rows.
The contextual model is a transparent, shrinkage-based starting hypothesis,
not a calibrated player projection system; meaningful predictive validation
and position/role/context-aware upgrades are still required.

Next: ingest legitimate 3-season NHL game logs with audit source metadata,
verify day-specific pregame availability and roles, then add team interactions,
goalie and PP/PK estimates. Never label simulations as validated without
out-of-time evaluation and frozen records. No market odds.
