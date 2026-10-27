# Shared Availability & Opportunity Allocation Engine — 2026–27.1

**Scope**: NBA, NFL, NHL and association football (soccer). Tennis is excluded.

## Sequence

1. Capture evidence timestamp prior to tipoff/kickoff. Resolve official roster and cascade sourced confirmed/projected injuries and participants. Preserve provenance, unresolved names and conflicts.
2. Resolve active/inactive/questionable statuses: inactive = zero; questionable = separate active/inactive scenarios, unless official evidence resolves it. Missing = unresolved, never silently available.
3. Estimate each eligible athlete's **prior opportunity weight**, conditional on teammates in/out, role, recent coach usage and matchup. Derived only from historical pre-event samples. This PR supplies no trained weights: caller must provide them.
4. Declare sport-specific budget and unit; cap physical minutes and respect personnel role compatibility.
5. Allocate opportunities **jointly** using constrained proportional shares, redistributing inactive players' workloads; flag infeasible rosters/budgets.
6. Propagate scenario allocations to unit strengths and opponent matchup estimates, then pace/runs/possessions/drives, and only afterwards to independently validated win or prop probabilities.
7. Backtest walk-forward per season and role; compare against recent-minutes/usage baselines. Never use odds as inputs.

## Budget contracts

| Sport | Unit | Regulation budget |
|---|---|---|
| NBA | five-player minutes | 5 × 48 = 240 per team |
| NHL | skater ice-time | 5 × 60 = 300 skater-minutes (subject to manpower situations); goalie 60 only for a full game with one goalie and no empty net |
| Soccer | outfield+GK minutes | 11 × 90 = 990 player-minutes, normal 11-player regulation; red cards reduce budget |
| NFL | targets, carries, offensive/defensive snaps | **Observed or separately projected team opportunity counts**, not an invented universal fixed number |

The NHL fixed 300 estimate is **not** valid during penalties, 3-on-3 overtime, goalie pulls or other deviations. Treat it as a reference scenario, not a verified fixed invariant for all NHL games. NBA overtime and soccer extra time likewise require dynamic budgets.

## Honest limitations in PR #101

- Shared allocation primitive and conservative NBA adapter, not a fully integrated workflow replacement.
- Cannot guarantee on-court lineup/position feasibility: next sport adapters require lineup-compatible constrained optimization and contextual weights.
- No live source reconciliation, learned player substitution model, coaching usage effect, or availability impact calibration yet.
- No production probabilities, historical forecasts or player projections modified.

## Required follow-up

Build team-specific, timestamped eligible player pools and historical usage records. Train/test weights with teammate-conditioned availability; integrate source cascade; implement discrete lineup feasibility; then score each sport on immutable pre-event backtests.
