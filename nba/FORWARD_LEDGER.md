# NBA frozen prospective cohort: durable collection

The frozen protocol is `reports/nba-validation-2026-11-04/prospective_protocol.json`.
This implementation collects evidence for its UTC window [2026-11-05,
2027-02-03), excluding Knicks, without changing model coefficients or the
protocol. It does not certify the models or evaluate interim predictive scores.

## Operation after merge

`.github/workflows/nba-forward-ledger.yml` runs at 00:17, 06:17, 12:17 and 18:17
UTC, and supports manual dispatch. Only main's schedule/manual job can persist
files; PRs run tests with read-only repository permission. Runs are serialized,
not cancelled in progress. GitHub schedules may be delayed or missed.

Every run creates new JSON files in `reports/nba-forward/observations/` and
`reports/nba-forward/runs/`. No original observation is overwritten. The workflow
commits only this directory to main and also retains a 90-day artifact (the repository retention limit verified in the first main run). Failure
evidence is persisted even when source errors cause the capture step to fail.
A blocked push or total runner failure can still leave an operational gap; the
workflow fails rather than claiming durable success. A later capture cannot
create a pregame prediction for a game that has already started.

The pinned three historical seasons are audited as 30 teams × 82 games. Each
run refetches all current-season league dates from October 20 through tomorrow,
so an outage cannot silently skip a historical day. Only source-completed games
observed before the new emission can enter team state. A known source-day
failure blocks new forecasts in that run, while its scheduled events and source
errors remain archived. Requests preserve only sports fields, never odds.

All regular-season events from the provider are represented, including in-play,
completed, delayed/cancelled status and events without a forecast. Empty days
are explicitly recorded in source-day coverage. A malformed or potentially
truncated scoreboard is a source failure. ESPN classification and omissions
remain single-provider limitations requiring independent cohort audit; no claim
of complete official schedule verification is made (including cup-final or
postponement classification).

Before emitting, the runner verifies the protocol's model source hashes. It
computes only the frozen Elo and Challenger, timestamps the finished computation,
and refuses emissions if tipoff was crossed while calculating. Once any pair
exists for an event, later runs do not create another pair. The reconstruction
also selects the earliest valid emission by prediction time, with digest as a
deterministic tie-break. Model outcomes are counted once per event.

Completed outcomes are separate observations. Original forecasts remain intact;
conflicting final scores or changed home/away/tipoff remain unresolved review
cases rather than quietly updating the cohort. Pending results are not losses.
A fixture's missing pregame forecast remains in the observed eligibility count.
Source failure records remain visible even after later recovery.

No Brier, log loss, calibration or success-rate summary is published during the
registered window. After the window closes, the runner still does not
certify/evaluate automatically: a separate eligibility, sample and source audit
is required. Collection stops after a fixed 14-day settlement grace interval;
that cutoff is operational and does not extend the registered prediction window.
There is no automatic model promotion or interim stopping by performance.

## Initial evidence

The first live test completed 2026-11-05T00:21:08Z (21:21:08 Chile, November 4).
The cohort includes 15 pairs: the original 13 requested November 4 games and
2 November 5 games observed before tipoff. Current-season history had 107 finals.
No source-day request failed. All 15 outcomes were pending at that observation.

The first two November 4 games had already started when this work began. Their
probabilities were imported from the existing frozen archive, not recomputed.
`forward_import.py` verifies its digest and manifest, matches exact fixtures,
requires the imported file to equal its Git version and records the blob and
original commit timestamp (2026-11-04T21:18:50Z, before every imported tipoff).
Git metadata is repository provenance, not an independent timestamp authority.
The archive was emitted before protocol registration, but committed before
registration and before any cohort outcome. This adoption is explicitly recorded;
it must be reviewed in the independent eligibility audit rather than described
as newly collected post-registration forecasts.

## Reproduction and checks

```
python -m unittest discover -s nba/tests -v
python nba/forward_capture.py --run-id manual-unique-id
```

`forward_import.py` is a one-time migration already represented in the committed
ledger. A repeat refuses to overwrite its file. Network capture always appends
new evidence; it must not be used to recreate earlier observations.

The reconstruction can be reproduced offline:

```
python - <<'PY'
import json,sys
from datetime import datetime,timezone
sys.path.insert(0,'nba')
from forward_ledger import load_observations,reconstruct
protocol=json.load(open('reports/nba-validation-2026-11-04/prospective_protocol.json'))
report=reconstruct(load_observations('reports/nba-forward'),protocol,datetime.now(timezone.utc).isoformat())
print({k:report[k] for k in ('scheduled_games_observed','paired_games','settled_paired_games','missing_pregame_games')})
PY
```

Tests cover original pretip provenance, no post-start creation, crossing tipoff
during calculation, earliest emission, one outcome per game, duplicate archive
copies, missing predictions, live status, changed fixtures, conflicting finals,
protocol/hash tampering, source failure, source truncation and embargoed metrics.
