# NBA: first learned conditional-minute component

This research module predicts **reported minutes if a player participates**.
It does not predict participation, assign starters, certify an active bench,
allocate a complete regulation rotation, or change Elo/Challenger, ML or +20.
The web is unchanged by this work.

## Data and temporal design

Source: the preserved 107 ESPN completed-game boxscores in
`reports/nba-2026-11-04/boxscores.json`: 2,413 recorded appearances and 489
explicit DNP rows. Both teams and the league-wide observed sample are included.
The source was collected after these historical events, so this is a
**retrospective reconstruction**, not point-in-time certification.

`reports/nba-minutes-research-2026-11-05/protocol.json` was saved before this
experiment's error metrics were calculated. It records the exact input-file hash,
fixed features, split boundaries and lambda grid. Registering it now does not
make the already completed historical games an independently untouched test.

- Train: tipoff before 2026-10-29T00:00Z — 273 scored player appearances, 19 games.
- Validation: October 29–30 UTC — 280 scored appearances, 15 games.
- Test: October 31–November 3 UTC — 612 scored appearances, 31 games.
- Other appearances provide warm-up or have insufficient prior history. Coverage
  and exclusions are recorded for every source game rather than dropped silently.

For each team, the prediction universe is built from players seen in **prior**
games; no target-game player roster or starter flag supplies features. Require
at least three same-team appearances. Features are last observed minutes,
means of last three and last five appearances, number of prior appearances
(capped at ten), and elapsed days since the last appearance (capped at fourteen).
A six-hour post-tip delay is used conservatively when reconstructing historical
availability of prior boxscore data. This is an explicit timing approximation,
not a claim of original provider publication timestamps.

After freezing the features, the scorer joins the target boxscore. Only measured
appearances are scored. DNP, absent player rows and missing minutes are not
converted into zeros or evidence of health. The error measures therefore apply
to this conditional component; they must not be described as full-roster or
unconditional minutes accuracy.

## Learned candidate and comparison

A pooled ridge regression standardizes features using training rows only and
leaves its intercept unpenalized. Lambda is selected from 1/10/100 by validation
MAE. The selected value is **10**; then the fit is rebuilt using train plus
validation only (553 observations). Test targets never fit coefficients or
choose the penalty. Current-game results enter future rolling features only
after the stated historical-delay rule, as they would in a sequential forecast.

| Model | Test MAE (minutes) | Test RMSE (minutes) | Mean bias |
|---|---:|---:|---:|
| Mean last five appearances | 4.7682 | 6.4062 | -0.8314 |
| Last appearance | 5.4428 | 7.2135 | -0.1683 |
| Ridge candidate | 4.7014 | 6.1057 | +0.0396 |

Positive gain favors the candidate. Paired whole-game bootstrap, 2,000 replicates,
seed 20261105:

- MAE gain 0.0668 minutes; 95% interval **[-0.1234, +0.2660]**.
- RMSE gain 0.3005 minutes; 95% interval **[+0.0128, +0.6336]**.

The primary MAE improvement is uncertain and very small. **Do not promote this
candidate or replace the current reference.** The RMSE result is encouraging
but does not establish generalization, independence or a full rotation model.
The sample is one short early-season window; whole-game clustering does not
remove repeated-player/team dependence across games. No alternative features or
penalties were selected by inspecting these test results.

Targets and predictions include reported total-game minutes, including overtime,
with the existing source contract's 0–65 range. They are not 48-minute
regulation allocations and do not sum to 240 per team.

## New prospective research emission

`minutes_prospective.py` saves a separate immutable research emission for the two
future games already observed by the forward cohort. It uses real source
collection timestamps no later than its emission, prior same-team minute records
(including archived completed player games), and roster observations before
future tipoff. The initial file contains 69 roster members: 52 conditional
estimates and 17 PASS for insufficient history.

Each player keeps `expected_game_minutes` and `participation_probability` null;
each team keeps regulation allocations null. Reported supplementary Out/unknown
states remain context and do not silently become a playing probability or a
zero-minute forecast. No candidate output is wired to the web or frozen MLs.
The two-game file is evidence for a future diagnostic, not a new independently
validated model or a replacement for the registered ML protocol.

## Reproduce

```
python nba/minutes_research.py \
  --archive reports/nba-2026-11-04/boxscores.json \
  --protocol reports/nba-minutes-research-2026-11-05/protocol.json \
  --output /tmp/nba-minute-evaluation.json --summary /tmp/nba-minute-evaluation.md
python -m unittest discover -s nba/tests -v
```

New files are created exclusively. The manifest identifies all archived research
artifacts; numerical replay tolerates 1e-10 for platform floating-point variation.
Tests explicitly change test outcomes and verify that fitted coefficients and
validation selection do not change, reject duplicate/invalid data, keep DNP and
missing history outside false zero labels, and reject future-collected inputs
for a live research forecast.

## Next model work

1. Accumulate a longer history and evaluate the same frozen conditional model
   on future appearances, including role/minute bands and team-specific coverage.
2. Establish a defensible pregame roster and participation target; model the
   probability of playing separately rather than using future appearance lists.
3. Couple eligibility, restrictions, positions and conditional weights in the
   240-minute team allocator; evaluate complete rotations and substitution.
4. Only then estimate injury/replacement effects and their incremental value on
   sporting efficiency and ML, keeping the registered statistical models frozen.
