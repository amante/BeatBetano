# NBA 2026-27: reproducible slate, November 4

The consolidated research archive is `reports/nba-2026-11-04/`. Its snapshot
was frozen at 2026-11-04T21:16:17.075599Z (18:16:17 Chile), before the first
tipoff at 2026-11-05T00:00Z (21:00 Chile on November 4). ESPN's league date
is November 4; these games occur on November 5 UTC. Chicago–Knicks is excluded.

## What actually executed

- Existing `prospective.generate`: Official candidate Elo benchmark and
  experimental Challenger rolling-margin/rest, unchanged coefficients.
- Three complete cleaned historical seasons: 3,690 games, each season 30 teams
  × 82 games; the existing cleaner excluded 11 non-regular-season events.
- 107 completed 2026-27 games through November 3, with both teams' boxscores and
  individual player minute observations. No summary request failed.
- Current ESPN roster membership: 26 teams, 452 player entries. This is not
  confirmation of the active roster. RotoWire projected starters remain
  attributed provider observations, including abbreviated names. Team aliases
  that do not match the feed remain uncovered; no fuzzy identity inference.
- Schedule-adjusted descriptive ratings, projected game possessions, and PPP
  are calculated by `reproducible_slate.py`, separately from the frozen MLs.

No full sporting-model prediction is certified. **All 13 games remain PASS for
the complete model**, including both teams' final ML and reaching a +20 lead.
Bench membership/roles, final minute allocations and injury replacement
coefficients have not been verified. Historical minute means are observations,
not projections, and are printed for every roster member with a sufficient
sample (minimum 3 appearances; last 5). Missing observations stay null.

## Reproducible calculations

For each historical game, estimated possessions are the existing ESPN boxscore
formula `FGA + .44*FTA - ORB + TOV`. Use the mean of both teams' estimates as
common game possessions `P_g`. Raw team ORtg and DRtg are respectively
`100*sum(points)/sum(P_g)` and `100*sum(opponent points)/sum(P_g)`.

League rate `L = 100*sum(team points)/sum(team possessions)`. For each team-game,
calculate the opponent's ORtg and DRtg over other observed games, **excluding
that game**. At least 2 other opponent games are required. The one-step,
possession-weighted schedule residual estimator is:

```
adjusted_ORtg_i = L + sum_g P_g*(100*points_i_g/P_g - DRtg_opponent_excluding_g) / sum_g P_g
adjusted_DRtg_i = L + sum_g P_g*(100*points_opponent_g/P_g - ORtg_opponent_excluding_g) / sum_g P_g
```

At least 3 usable games are required. The report retains sample counts and game
IDs. This is a descriptive schedule adjustment, not a fitted causal model;
it does not identify player availability effects. It uses the current-season
sample only, with no undocumented prior-season blend or shrinkage weight.

The exploratory possession projection is the mean of both teams' historical
possessions per game. `PPP_i = (adjusted_ORtg_i + adjusted_DRtg_opponent)/200`;
`points_i = projected_possessions*PPP_i`. These are declared research heuristics,
not validated forecasts. Overtime is not normalized to 48 minutes. Both teams
receive the same expected possession count; no combined-total/pace confusion.
Availability-adjusted ORtg/DRtg remain null.

## Injury × Replacement Impact and +20

Existing roster resolution, joint-minute budget and on/off scenario modules are
run for **both teams in every game**. Unknown availability blocks allocation;
questionable states are not assigned guessed probabilities. The archive retains
the reasons and all unresolved player IDs. Existing scenario outputs are not
relabelled as an injury-impact fit. No player, replacement or simultaneous-absence
interaction coefficients have been trained and independently validated. Their
rating and probability deltas remain null rather than assuming additive effects.

The official injury index returned HTTP 403. The supplementary ESPN injuries
adapter returned no resolved player claims for this slate. Neither silence nor
roster membership means healthy. `source_failures.json` preserves the failure.
Previously asserted injuries in the referenced chat are not accepted as evidence.

`P(reach +20)` means a team's lead reaches at least 20 at any point, including
overtime; it is not `P(final margin >=20)`. Both teams can reach +20 in the same
game. ML complements are valid; +20 complements are not. There is no historical
score-path training/calibration dataset here, so +20 is PASS for both models
and both teams. No normal-margin approximation or arbitrary sigma is used.

## Reproduce without network or changing the capture

From the repository root:

```
python nba/reproducible_slate.py \
  --snapshot reports/nba-2026-11-04/snapshot.json \
  --boxscores reports/nba-2026-11-04/boxscores.json \
  --roster reports/nba-2026-11-04/roster.json \
  --lineups reports/nba-2026-11-04/lineups.json \
  --availability reports/nba-2026-11-04/availability.json \
  --minutes reports/nba-2026-11-04/minutes.json \
  --scenarios reports/nba-2026-11-04/scenarios.json \
  --output /tmp/nba-reproduced.json --summary /tmp/nba-reproduced.md
python -m unittest discover -s nba/tests -v
```

Outputs use exclusive creation; choose new output paths. Recompute the frozen
MLs with `prospective.generate(history, fixtures, snapshot.created_at_utc)`;
its digest must equal the archived snapshot digest. `manifest.json` records
SHA-256 of every source/derived artifact before manifest creation. Scoreboard
and summary adapters whitelist sports fields; bookmaker data is not archived
or consumed as model input.

For a **new live capture**, use a new empty directory while these games are
still pregame (these two collectors are intentionally scoped to this date):

```
python nba/capture_nov4_evidence.py --output-dir /tmp/nba-new-capture
python nba/run_nov4_slate.py --output-dir /tmp/nba-new-capture
```

These commands use actual collection time; they cannot reconstruct historical
availability after tipoff. Repeated capture never overwrites the original.
No web publication, model promotion or merge is performed by this PR.

## Validation limits

Unit tests and exact replay establish arithmetic, identity, missing-data,
minute-budget, hash and timestamp controls. They do not validate predictive
calibration. Today's outcomes were unavailable at freeze. No postgame accuracy,
Brier improvement, or sporting-model superiority is claimed. Existing Elo and
Challenger outputs are compared on the same 13 fixtures only as diagnostics.
