# Availability Delta 2.1: evidence gate

First audit independently sourced, point-in-time pregame statuses using:

```
python validation/availability_audit.py --games GAMES.csv --reports STATUS_SNAPSHOTS.csv --output results/availability_audit
```

Use source files legally obtained outside the pipeline; never infer target-game injury status from postgame snaps. Require both teams' pregame snapshots. The resulting report records missingness by season and can be used to establish whether a paired out-of-sample study is feasible.

**No historical injury snapshots have been fetched or validated in this branch.** No calibrated change to ML, spreads, CB1/CB2/nickel or receiver props is justified yet. Injury labels alone cannot distinguish starters, replacements, expected snaps or coverage assignment.

Once proper source and full coverage are available:
1. Join only true as-of kickoff snapshots; check observation time and player/team identity.
2. Tag starter role and replacement ability using independent past-game information, not outcome hindsight.
3. Fit EPA + availability on past training seasons and evaluate strictly future holdout.
4. Compare on exactly the same set of games, report selection bias and bootstrap paired confidence intervals.
5. Consider promotion only after an independently repeated improvement.
