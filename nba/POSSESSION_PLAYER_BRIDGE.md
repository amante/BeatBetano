# Verified possession / player-effect bridge

This change connects a separately verified normalized possession/lineup export to
the existing sporting research engine. It does not download history, reconstruct
missing sources, parse raw ESPN shots as possessions or authorize production.
Existing frozen-history/daily-delta behavior remains in place.

## Input and execution

```sh
python nba/possession_player_bridge.py \
  --snapshot /path/to/frozen-pregame-baseline.json \
  --context /path/to/verified-roster-rotation-role-context.json \
  --possessions /path/to/verified-normalized-possession-export.json \
  --boxscores /path/to/paired-historical-team-boxscores.json \
  --output-dir /path/to/new-bridge-output
python -m unittest discover -s nba/tests -v
```

Python 3.9+, repository requests dependency. No additional numerical dependency.
The output directory must be new. Outputs include sealed evidence, bridge audit,
sporting snapshot and original normalized/context inputs. Historical replays use
the real emission clock and remain `retrospective_replay`.

The possession input uses the existing `possession_path_features.py` contract:
`games` with fixture identity, completed time, complete possession sequence,
non-tied reconciled final scores, duration and per-game evidence. Each possession
has contiguous `sequence`, offensive `team`, integer `points` in [0,4] and boolean
`turnover`. The exporter must have reconciled free throws, technicals, offensive
rebounds and period boundaries before export. An offensive rebound extends the
existing possession; it cannot be treated as a new possession.

The bridge additionally requires root `evidence` with verified source URL,
source SHA-256, availability and observation times. Each historical game needs:

- `team_rosters`: both team IDs mapped to complete historical player-ID lists;
- `lineup_evidence`: the same provenance structure, observed before the cutoff;
- `lineup_attribution: "possession_start"`;
- every possession's `offense_lineup` and `defense_lineup`: five unique player IDs
  belonging to the corresponding historical roster. Substitutions during a
  possession retain the explicitly declared possession-start attribution.

The input schema asserts source verification; it cannot prove source truth or
licensing by itself. Inspect the underlying authorized exports. Raw play-by-play
or a reconciled scoring path cannot substitute for these possession/lineup fields.
There is no automatic source for normalized possessions introduced by this PR.

Context is bound to the frozen baseline's `content_sha256` through
`snapshot_sha256`. Its `games[game_id].teams[team]` entries retain the existing
verified roster, injury, lineup and rotation fields: all players, statuses,
reference minutes/usage, caps, independently supplied replacement quality and
four role scores. The bridge fills path metrics and fitted player effects only.
It does not derive replacement quality, roles, availability or confirmed starters
from boxscore production. Missing any roster player's fitted effect blocks that
team, including absent and bench players.

## Experimental adjusted effects

`player_possession_effects.fit` jointly estimates:

```
100 * possession_points = intercept + home_offense_coefficient
                       + sum(five offensive player coefficients)
                       + sum(five defensive player coefficients) + residual
```

The objective is squared error plus `1000 * sum(nonintercept coefficient^2)`.
The home coefficient is penalized too. A sparse conjugate-gradient solver checks
convergence against relative normal-equation residual tolerance 1e-9, maximum
500 iterations. There is no outcome-driven parameter search. Fixed regularization
and sample thresholds are research policy, not validated hyperparameters.

Offense coefficients measure associated additional points per 100 possessions;
positive defense coefficients mean additional points allowed. They account jointly
for recorded teammates and opponents, but lineup collinearity remains confounded.
They are **not causal injury effects or raw on/off differences**. Output fields
therefore use `effect_kind: regularized_possession_effect_v1`,
`offense_effect_per_100`, `defense_effect_per_100` and
`effect_sample_possessions`, separately from the legacy adjusted-on/off fields.

A player needs at least 100 offensive and 100 defensive possessions, three games,
and at least one observed off-court possession on each side. Effects outside
[-30,30], absent IDs, insufficient samples and solver failures are unsupported,
not zero-filled. These gates do not establish statistical identification.

The engine's existing sample shrinkage n/(n+1000) additionally applies to these
regularized coefficients before minute-delta aggregation; this is deliberate
extra conservatism and still requires independent evaluation. Existing legacy
adjusted-on/off behavior is retained. Fit method and parameters enter the sporting
snapshot parameter hash; mixed fit policies in a slate are rejected, and existing
backtesting rejects mixed parameter hashes.

## Validation and current limits

Tests cover an analytic ridge solution, reproducibility, lineup identity,
source timestamps, sample gates, both opponents, missing replacement context,
legacy/new effect definitions, parameter lineage, CLI snapshots and overwrite
rejection. Synthetic complete inputs connect to the engine and produce research
calculations while production remains PASS. They do not validate real accuracy.

The archived November 4 replay contains 13 fixtures but no verified normalized
lineup-possession export or complete player context. The bridge returns 13/13
PASS and zero connected games. The two raw scoring paths captured November 6
also lack those normalized lineup-possession records. They are not repackaged as
training examples. Real adjusted-effect fitting, walk-forward validation and
production promotion still require the missing dated exports.

Definitions: [NBA statistical glossary](https://www.nba.com/stats/help/glossary).
Methodological background: [Sill, regularized adjusted plus-minus](https://www.sloansportsconference.com/research-papers/improved-nba-adjusted-using-regularization-and-out-of-sample-testing).
This implementation is our experimental possession-level model, not a reproduction
of Sill's fitted model or an assertion of its published performance.
