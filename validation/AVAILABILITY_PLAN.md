# NFL Availability Delta: source audit and promotion gate

This branch introduces a pregame **data contract and leak-proof feature extraction**, not a trained Availability Delta predictor.

## Verified source constraints
- nflverse states its historical injury-report feed stopped after 2024; there is no nflverse 2025 injury feed. Do not manufacture 2025 records.
- nflverse 2023+ participation data is published after the season; using target-game participation in a pregame forecast would leak future information.
- Postgame snap counts can describe a *prior* game, but cannot establish target-game availability unless the relevant snapshot preceded kickoff.

See https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html

## Required pregame status snapshot schema
`game_id,team,player_id,position,status,snapshot_utc,kickoff_utc,source`

Only observations at or before kickoff qualify. Missing coverage => exclude from the availability comparison, never assume fully healthy.

## Experiment after real data obtained
1. Establish starter quality and replacement tiers from **prior games only**, without outcome-derived rankings.
2. Compare baseline EPA challenger vs EPA + injuries/availability on IDENTICAL coverage games. Preserve fixed 2024–25 holdout only if sufficient pregame snapshots exist for BOTH years. Otherwise explicitly narrow the holdout and report sample selection.
3. Label nominal position effects separately: QB, OL, EDGE, DT, LB, CB, S. CB1/CB2/nickel labels need lineup-role snapshots, not position CB alone.
4. Compare held-out Brier, log loss, reliability, coverage, and bootstrap paired uncertainty; require no leakage.
5. Only then consider ML/spread adjustments and player props. A player marked OUT is not necessarily a *starter*.

This version has no inferred CB1/CB2/nickel roles and **no numerical effect assigned to an absent player**.
