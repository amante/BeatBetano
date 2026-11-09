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

## Compatibility with the V2 engine

The bridge carries `turnover_adjustment_method` from the shared path extractor
alongside the opponent-adjusted turnover/transition features. It never borrows a
method marker from supplied context for rates derived elsewhere. The player-effect
adapter retains both regularized coefficients and legacy adjusted-on/off support;
V2 fatigue, committed/forced turnover and replacement inputs remain mandatory.
Context must therefore include verified schedule evidence, the target tipoff,
previous-game schedule and individual 48-hour minute load, plus committed/forced
turnover on/off estimates. The bridge does not infer those inputs from scoring
coefficients. Missing inputs leave that team disconnected and the fixture PASS.

Sporting snapshots retain the Official/Challenger track labels and hash the full
V2 engine parameters together with the player-effect fitting policy. Regression
checks exercise a connected export without a context method marker, preservation
of fatigue/turnover inputs, and rejection of missing schedule/load evidence.

## Capture NBA LiveData possessions

The optional importer uses the NBA LiveData play-by-play and final boxscore and
the upstream pbpstats parser. It retains the source JSON files and their
digests in the capture. The observation time is the actual fetch time. Use a
forecast cutoff after the capture and before the target tipoff.

```sh
python -m pip install pbpstats==1.3.11
python nba/capture_possessions.py --game-id 0022600002 --output-dir /path/to/new-capture
```

Pass the resulting `possessions.json` to the bridge. The importer preserves NBA
player IDs. The daily availability capture uses ESPN IDs, so joining them
requires a separately verified crosswalk. Capture one or more distinct NBA
regular-season IDs. The report lists rejected games individually. It requires a
final score match and five roster members on each side at the first live action
of each possession. It rejects score changes the engine cannot represent, such
as points by the defense or points on a turnover possession. Parser failures
are excluded and can affect the composition of any research sample.

## Audit current-roster coverage

Use the saved baseline, player crosswalk and availability artifacts from the
same daily run. Capture historical NBA IDs from that run's team-metrics
bindings, then run:

```sh
python nba/player_possession_coverage.py \
  --snapshot /path/to/forecast.json \
  --crosswalk /path/to/forecast.team-metrics/player_crosswalk.json \
  --availability-dir /path/to/forecast.availability \
  --possessions /path/to/capture/possessions.json \
  --output /path/to/new-player-coverage.json
```

Run before tipoff. The audit uses the existing sample thresholds and checks
that the fitted player appeared for the relevant team. The provider starter
flag may represent a projection. A historical rotation entry has a minutes
estimate and does not identify a specific injury replacement.

November 9 pilot: 16 of 50 requested games normalized, yielding 3,249
possessions across 224 players. Among 281 current roster entries for eight
fixtures, 235 had linked IDs and seven supported research effects. Coverage was
2 of 39 provider starter entries and 5 of 151 historical rotation entries.
The pilot did not establish a full two-sided rotation adjustment or emit
an updated ML/+20 probability.

The expanded November 9 pilot requested 68 additional completed games
involving at least one of the 16 target teams, using the same official
schedule and league-date cutoff. Across both batches, 44 of 118 games
normalized and yielded 8,869 possessions. Recognizing explicit team fouls
and jump balls tipped to a team recovered five previously rejected games.
The fit covered 24 of 39 provider starter entries and 80 of 151 historical
rotation entries. Four of eight fixtures had supported effects on both
sides. That coverage does not establish replacement roles or minutes/usage
redistribution, which remain required for a full adjustment.
