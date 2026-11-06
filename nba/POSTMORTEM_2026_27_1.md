# NBA 2026-27 / Challenger 2026-27.1 — consolidated November 4 follow-up

This implementation is a **research candidate**. Sporting recommendations are
**PASS for both teams, every fixture, ML, reaching +20 and DUAL**. Unit tests
verify calculations and controls; they do not establish predictive calibration.
No current model promotion or merge is authorized by this change.

## Existing implementations retained

The audit used GitHub main `decff7873efc1a572946c2921afc80ebc9b011b1`, which
is ahead of the desktop checkout. The following modules are reused, not replaced:

| Existing component | Role in this change |
|---|---|
| `prospective.py`, `challenger.py`, `guardrails.py` | Unchanged Elo, margin/rest Challenger and hybrid baselines |
| `reproducible_slate.adjusted_ratings` | Shared possession-weighted schedule residual estimator |
| `rotation_allocation_adapter.project_nba_minutes` | Shared capped regulation-minute allocator |
| `availability_scenarios.py`, `absence_conditioned_minutes.py` | Existing descriptive availability research remains available; not mislabelled as fitted impact |
| `forward_ledger.py`, `sporting_archive.py` | Existing first-emission ledger and source archives remain unchanged |
| `nba_hoy.py` | Mandatory post-mortem publication gate; legacy impact flags cannot authorize a final ML |
| `daily_pipeline.py` | Creates a separate sealed sporting companion alongside the unchanged baseline |

The previous `reproducible_slate.py` remains a replayable record of the earlier
research method. Its NULL player-impact/+20 fields are not retrospectively filled.
The new engine has no Knicks exclusion or favorite-only branch: all 30 teams use
the same rules.

## Executable components

`postmortem_engine.py` evaluates both complete rosters, actual absences and
replacement quality. Minutes sum to 240, every player is included (including
zero-minute absences and bench members), each player stays within a source-supplied
cap <=48, and usage shares sum to one. Allocation is infeasible if supported
capacity is insufficient. It decomposes minutes into five-player stints totaling
48 minutes and checks basic creation/rim coverage; these are feasible research
stints, **not observed or coach-confirmed substitution schedules**.

Questionable players on both teams generate joint in/out branches, at most three
unresolved players / eight branches. Branch weights remain NULL. The all-available
counterfactual and actual-availability forecast use common random numbers; their
ML, +20 and point deltas are explicit. Counterfactual starters are hypothetical,
not an assertion that an absent player is medically available.

`possession_path_features.py` accepts a verified, normalized possession export,
reconciles every final score, derives committed/forced turnovers, regulation pace,
post-turnover scoring, historical maximum leads and scoring-run blocks. It
requires publication/observation timestamps, completed games and contiguous
possession sequence IDs. This is **not a raw shot-event parser**: free throws,
offensive rebounds and technical fouls must be reconciled upstream. No new
unverified web scraper or guessed play-by-play data is introduced.

`score_path.py` simulates scoring paths with empirical four-possession blocks,
turnover events, transition contexts, randomized possession rounding and overtime
until an actual winner. It checks the lead after each possession, not only after
pairs of possessions. MLs are complementary; +20 probabilities are separate
first-passage events and can both occur. The output includes either/both +20,
simulation seed, method, sample count, overtime count and Monte Carlo standard
errors. Those errors quantify simulation noise, **not model uncertainty**.

`postmortem_backtest.py` scores frozen forecasts in chronological order without
refitting or selecting coefficients. All three baselines and the new candidate
are compared on the same eligible ML fixtures with Brier, log loss and reliability
bins. Maximum-lead outcomes require a complete score-path source; final margins
never substitute. +20 baseline comparison stays NULL because the old baselines
do not estimate that target. Coverage counts, exclusions, unmatched outcomes and
game-level contributions remain visible. Duplicate emissions must be resolved
under a preregistered rule upstream, rather than selecting the best one after
results. Mixed parameter versions are rejected.

## Reproducible model hypotheses

All constants are in `PARAMETERS`, serialized and hashed in each snapshot. They
are declared research hypotheses, **not estimates fitted to the November 4 errors**.

For each role r (creation, spacing, rim, rebounding), lost capacity is
`L_r = sum_absent baseline_minutes_i/48 * role_i,r`. Conditional minute weight is
`baseline_minutes_i * replacement_quality_i * exp(.8 * sum_r role_i,r * L_r)`;
without absences the baseline weight is retained. The shared capped allocator
redistributes the full 240-minute budget jointly. Usage weight is
`minutes_i * baseline_usage_i * exp(1.2 * sum_r role_i,r * L_r)` with caps
`minutes_i/48 * max_usage_i` and a one-possession total budget.

Player adjusted on/off effects are shrunk by `n_possessions/(n_possessions+1000)`.
The efficiency shift is the sum of
`(projected_minutes-baseline_minutes)/48 * adjusted_on_off * shrinkage`.
Defensive on/off is the difference in **allowed** points: negative is better.
Usage overload costs `8 * sum_i minutes_i/48 * max(0,new_usage-base_usage)^2`.
Residual role loss, after substitute coverage, costs
`3 * sum_r uncovered_role_r^2` on offense and half that on defense. These nonlinear
terms are sensitivity hypotheses; correlations in on/off are not causal effects.
Player inputs must be adjusted on/off estimates with a documented reference
rotation, not raw points per game or a player-name-based penalty.

Schedule-adjusted ratings are computed by the existing leave-one-game-out
opponent residual method. Add the player offense/defense deltas to the respective
team ratings. Matchup baseline PPP is
`(adjusted_ORtg_team + adjusted_DRtg_opponent - league_rating)/100`.
Projected possessions are the mean of the two **regulation-normalized** pace
inputs, not combined team possessions. Regulation points = possessions × PPP.
Definitions of [ORtg, DRtg and pace](https://www.nba.com/stats/help/glossary)
follow NBA units; the adjustment and projection formulas here are our hypotheses.

Matchup turnover rate `q` averages own committed rate and opponent forced rate.
The PPP correction is only the change from historical turnover rates:

```
non_TO_PPP = matchup_baseline_PPP / (1 - historical_own_turnover_rate)
delta_PPP = -(q - historical_own_turnover_rate) * non_TO_PPP
          + (projected_opponent_q - historical_own_forced_rate)
            * (1 - q) * transition_bonus
```

The simulator's non-turnover conditional mean is
`normal = projected_PPP/(1-q) - opponent_q*transition_bonus` and
`after_opponent_turnover = normal + transition_bonus`. Consequently the
unconditional mean remains projected PPP: points after turnovers are attributed
within total points rather than added a second time. Empirical blocks are tilted
as whole blocks using exponential weights to match these conditional means,
preserving their scoring order. Unsupported scoring means cause PASS; they are
never extrapolated beyond the block support.

## Input contract and provenance

Baseline input is the existing digest-verified prospective snapshot. Boxscores
use the existing paired `reproducible_slate` archive. Player/path evidence is:

```
{
  "snapshot_sha256": "<baseline content_sha256>",
  "games": {
    "<game_id>": {"teams": {"<home_team>": {...}, "<away_team>": {...}}}
  }
}
```

Each team requires:

- `roster_complete: true`, five unique `confirmed_starters`, all roster `players`.
- `roster_evidence`, `injury_evidence`, `lineup_evidence`, `metrics_evidence`:
  `verified: true`, HTTPS `source_url`, lowercase 64-character `source_sha256`,
  `available_at_utc`, `observed_at_utc`. Publication <= capture <= feature cutoff
  < tipoff. Current roster/injury/lineup evidence is at most six hours old.
- `metrics_through_utc` strictly before cutoff. Metrics provenance covers the
  player/role estimates as well as the normalized possession sample.
- Each player: `player_id`, status (`available`, `out`, `questionable`),
  `baseline_minutes`, `max_minutes`, `baseline_usage`, `max_usage`,
  `offense_on_off`, `defense_on_off`, `on_off_possessions`, `replacement_quality`,
  `roles` with all four role strengths in [0,1]. Reference minutes total 240;
  minute-weighted reference usage totals one.
- `pace_regulation`, `turnover_rate`, `forced_turnover_rate`, `transition_bonus`,
  `path_sample_possessions` >=100 and `non_turnover_blocks` with at least three
  observed length-four integer score blocks. The extractor requires at least
  three historical games and ten observations in each transition context.

No bookmaker field is consumed. Market-keyed payloads, nonfinite values, source
identity gaps, duplicate IDs, stale/future sources, insufficient replacement
capacity and unsupported empirical path distributions fail closed. Provenance
schema checks and hashes are **not proof of source truth, licensing, calibration
or a real historical publication**; the underlying authorized exports and raw
source digests still require audit. Never populate this contract from the prior
chat's unverified player or result assertions.

Snapshots contain the complete baseline, evidence and boxscore inputs, their
probabilities, timestamps, injuries, starting fives, rotation scenarios, parameters
and model version. They use exclusive file creation and a content hash. The actual
emission clock is distinct from the source cutoff: executing a historical replay
today sets `emission_kind: retrospective_replay` and is rejected as a prospective
backtest emission. The CLI never accepts a fake historical emission timestamp.
External pretip Git/publication provenance is still necessary for a prospective
performance claim; a self-reported timestamp and hash alone are insufficient.

## Run and review

Use Python 3.9+ locally (CI uses 3.11), with the repository's `requests` dependency.

```sh
python -m unittest discover -s nba/tests -v
python nba/postmortem_engine.py \
  --snapshot /path/to/frozen-baseline.json \
  --evidence /path/to/verified-team-player-path-evidence.json \
  --boxscores /path/to/paired-historical-boxscores.json \
  --output /path/to/new-sporting-snapshot.json
python nba/postmortem_backtest.py \
  --snapshots /path/to/pregame-1.json /path/to/pregame-2.json \
  --results /path/to/verified-results.json --output /path/to/new-evaluation.json
```

Result rows require exact game/team/tipoff identities, non-tied integer final
scores, `completed_at_utc` and the same evidence provenance fields. For +20 also
require `score_path_complete: true`, `home_max_lead`, `away_max_lead`.

The daily command automatically creates `<baseline-stem>.postmortem.json` and
the daily workflow archives both JSON artifacts. Optional `--postmortem-evidence`
and `--postmortem-boxscores` accept already bound verified inputs. Missing inputs
produce a complete slate of PASS records, retaining baseline diagnostics.
`nba_hoy.py --postmortem ...` displays research results but cannot promote them
through legacy validation booleans.

## Current evidence limits

The repository's November 4 archive contains 13 pregame fixtures and 107 prior
paired boxscores. It does **not** contain the complete verified player impact,
replacement role and normalized possession-path exports this candidate needs.
The archived official injury request failed with HTTP 403. The replay therefore
returns 13/13 PASS and no new numerical candidate predictions. It cannot recreate
missing pregame sources after those games. The prior chat's 6/9 qualitative ML
record is not used as a quantitative backtest or calibration target.

Synthetic tests exercise full calculations and path semantics. Actual multi-season
player/path backtesting, calibration, coefficient fitting, external holdout audit
and model promotion remain unavailable until the required authorized data exists.
No superiority, profitability or calibrated real-game +20 probability is claimed.

## November 5 follow-up — research V2

The existing engine, extractor, simulator, archive and evaluator are extended in
place. Official 2026-27 remains the existing Elo benchmark; Challenger 2026-27.1
is the uncalibrated V2 research candidate. Baseline +20 stays NULL when unavailable.
No production coefficients or baseline probabilities are silently replaced.

`postmortem_validation/nov5_observed_evidence.json` records the user-supplied
November 5 evidence: Orlando 104–117 Phoenix, PHX maximum +30 despite final +13;
Miami 100–120 Golden State, GSW +20. It includes Orlando's Banchero/Suggs/Isaac
absences, PHX 17/34 triples, Orlando's 25 turnovers and PHX's 36 points after
turnovers; GSW's Butler/Porzingis/Moody/Santos absences, Giannis available for
Miami, Miami back-to-back following overtime, and GSW two days' rest.
These statements have not been independently reconciled with a licensed raw
export in this change. They are separate observed evidence, never player features
or fabricated prospective snapshots. Both models' four pregame probabilities,
hits, DUAL, Brier and log loss remain NULL. Unknown opposing maximum leads remain
NULL too. Regression witness paths test the reported boundaries; their possession
order is synthetic, not historical play-by-play.

### Added input requirements and explicit hypotheses

Both rosters now require player `forced_turnover_on_off` (forced rate delta,
[-.2,.2]) and `turnover_on_off` (committed turnover rate delta,
[-.2,.2], with the same adjusted reference rotation and shrinkage as efficiency)
and `minutes_last_48h` ([0,106], reliably observed minutes). Reference-minute
changes propagate turnover effects; usage overload adds `.02 * overload` to the
committed rate. Insufficient or unknown replacement data still means PASS.

Both teams require `schedule_evidence` with the same timestamp/source contract,
`target_tipoff_utc` equal to the fixture, and `schedule` containing
`previous_tipoff_utc`, `previous_completed_at_utc`, `previous_overtime_periods`.
Previous completion must precede the source publication. Back-to-back is an
explicit <=30 hour tipoff gap, avoiding UTC calendar-day assumptions. Schedule
pressure = `max(0,(48-hours_since_completion)/24) + .25*prior_OT` (OT term only
on back-to-back). Rotation load = sum of projected-minute shares times
`max(0,minutes_last_48h/48-.5)`, divided by five. Their sum is fatigue index F.
Offense shifts by -F/100 PPP, allowed defense by +.5F per 100 and committed
turnover rate by +.005F. Actual minute caps remain source supplied; the model
does not invent medical restrictions. Deep rested replacements reduce projected
load through the existing allocation, usage, on/off and rebounding role system.
These constants are declared sensitivity hypotheses, not fitted findings.

`possession_path_features.extract` now centers committed rates on opponents'
forced rates, and forced rates on opponents' committed rates, using historical
possession exposure and the archive league mean. Transition bonus similarly
subtracts exposed opponents' allowed-context bonus and adds the league context
bonus. Raw rates and expected opponent rates remain visible. The engine requires
`turnover_adjustment_method: opponent_residual_v1`; missing inputs or adjusted
rates outside supported bounds cause PASS, without clipping. This descriptive
one-step adjustment is not a causal or fitted schedule-strength estimate; sparse,
unbalanced and disconnected samples need further validation.

The existing frozen-snapshot evaluator supplies chronological walk-forward scoring,
paired baseline comparisons and reliability bins; it does not train a calibrator.
No recovered prospective forecasts or verified player/path dataset for these two
games exists here, so empirical performance and fitted calibration remain
unavailable. No November 5 result is used to tune constants. V2 snapshots have a
new version and parameter hash; older V1 snapshots remain immutable and must be
evaluated using their corresponding evaluator version. All recommendations PASS.
