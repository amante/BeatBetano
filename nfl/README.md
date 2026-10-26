# NFL hoy — first operational NFL pregame stage

Invoke **NFL hoy** by running the `NFL hoy — odds-free prospective slate`
workflow with a YYYY-MM-DD NFL calendar date.

It retrieves the current ESPN scoreboard, excludes already started games,
and builds a *candidate* Elo probability from completed historical nflverse
games using game-date frozen updates. It saves results to `results/nfl/nfl_hoy.json`.

Scope: complete coverage only **relative to parsed ESPN scoreboard events**;
no guarantee of complete league-wide fixture coverage. The NFL Elo is NOT a
certified or injury-adjusted official 2026-27 probability. It does NOT
calculate receiving, rushing, tackles, kickers or 13-leg betbuilder props.

Next integrated NFL release: resolve starter availability (QB/OL/EDGE/DT/
LB/CB/nickel/S), verified inactives, forecasted weather, opposing coverage,
snap/usage projections and a separately validated challenger. Never
manufacture absent data or use odds as a model input.
