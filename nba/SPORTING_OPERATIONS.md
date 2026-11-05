# NBA: operational publication and periodic sporting evidence

This connects the frozen forward ledger to the NBA screen and adds a separate
sporting evidence cycle. Neither frozen model source nor protocol coefficients
are changed. No new sporting probability, +20 estimate or calibration is fitted.

## Verified operation

The existing main workflow was manually dispatched on November 5 at 03:23 UTC:
https://github.com/amante/BeatBetano/actions/runs/41961290170
Both jobs succeeded, and commit `0d03bb6` persisted the new observation and
cohort reconstruction in main. It recorded 15 paired events, 5 settled pairs,
and zero missing pregame pairs. This verifies a real main execution and push,
not merely the PR test job. The six-hour cron has not been claimed as observed.
GitHub capped artifact retention at 90 days; the workflow now requests that
actual limit. The durable source remains the append-only repository archive.

## New connections, active after this PR merges

The six-hour main workflow now runs:

1. Existing frozen Elo/Challenger capture and cohort reconstruction.
2. `sporting_cycle.py`: select still-pregame fixtures with a recent schedule
   observation; archive current rosters, attributed injuries and provider
   starting fives, attempt the official report, and collect player boxscores for
   newly settled paired games.
3. `forward_publication.py`: reconstruct the complete observed cohort, select
   the latest sporting observation strictly before each tipoff, and publish
   `frontend/data/nba-forward-latest.json`.
4. Persist the forward archive, sporting archive and public packet together;
   retain source failures, and refresh Pages through the forward workflow's
   completion event. Scheduled Pages refresh remains a recovery path.

The public packet is a derived view and may be replaced by later views. Its
source observations are create-only and manifest/digest checked. Publication
cannot alter the original per-game probabilities or their emission timestamps.
The earlier manual `nba-auto-history.yml` publication contract remains separate;
the NBA screen now explicitly consumes the accumulated forward contract.

NBA cards show Elo and Challenger for both teams, original emission time,
latest source capture, final scores when available, missing forecasts, source
conflicts, stale capture warnings and sporting evidence with its own timestamp.
They do not present the historical hybrid as a model in the registered forward
comparison. A source state is described as of its last observation, not as a
live scoreboard. No aggregate hit rate, Brier, log loss or calibration is exposed
inside the embargoed protocol window.

The calendar view uses Chile dates. A Chile day can overlap two US league days;
empty and not-yet-covered dates are distinguished using that overlap. For
example a US late game can appear on the next Chile calendar day.

## First sporting cycle

At 2026-11-05T03:27:38Z, the independent new cycle archived:

- Three pregame games: one late November 4 league game and two November 5 league
  games. Six roster snapshots, 105 players and 16 matched supplementary Out claims.
- 89 roster members still lacked explicit individual availability; zero teams
  qualified for a complete minutes allocation.
- Five completed paired games with player boxscores; 135 player-team-game rows.
  All 135 can be linked to an earlier roster observation, but only 9 have an
  explicit supplementary pregame status. Missing DNP minutes remain null.
- The official index again returned HTTP 403, recorded in `official_source.json`.
  Provider observations are not promoted to official active/out verification.

Evidence is under `reports/nba-sporting/`. Actual target files have SHA-256 integrity references checked before each join. Source failures remain retriable;
failed player-boxscore requests do not create a successful game archive. Only
successful game IDs are skipped in later cycles. Fixture/final-score mismatches
are recorded instead of joining incompatible targets.

## Player-game history is a foundation, not an impact fit

`player-ledgers/` contains **pregame context** in separate fields from
**postgame minute targets**, with independent timestamps and source references.
Late observations cannot become pregame context. Unknown does not mean active;
DNP does not prove an injury; postgame starter flags are labelled postgame.
No row is certified for availability-impact training. The next modeling stage
must establish historical coverage, role/rotation features, minute-budget and
position constraints, then evaluate minutes out of sample before replacement
or probability effects are considered.

## Failure behavior and remaining coverage gaps

- No source packet or malformed packet: no old emission is silently substituted
  into the new screen.
- Missing pregame pair or changed fixture: explicit PASS; no invented probability.
- Invalid sidecar manifest or unavailable source: evidence gap remains visible.
- Partial/missing availability: no assumption that the bench is healthy and no
  sporting adjustment to registered model probabilities.
- Schedule/runner gaps and single-provider omissions remain audit issues.
- The sports cycle stops after the same fixed 14-day settlement grace period;
  the final publication is retained. No interim performance-driven extension.

## Validation

Run `python -m unittest discover -s nba/tests -v`, frontend Python tests, and
`node --test frontend/tests/nba-forward.test.cjs` using Node 22. Tests cover
strict pretip selection, missing statuses, DNP nulls, actual-target chronology,
manifest failure, original ML preservation, Chile dates, stale data, invalid
contracts, missing pairs, fixture conflicts and no interim metrics. A local
isolated component preview verified the rendered timestamps and paired MLs;
the production screen change awaits merge and deployment.
