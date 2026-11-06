# Point-in-time experiments

`walk_forward(events, factory, feature_names, ablations)` evaluates one binary
sport/market at a time for NBA, NHL, NFL, soccer and tennis. It reuses
`data_lineage.verify_manifest`, `calibration_audit.score` and registry sport IDs.
Existing official pipelines, coefficients and model registry are untouched.

Each event supplies `event_id`, `sport`, `market`, `season`, `features`, binary
`outcome`, `settled_at_utc`, and the existing lineage `manifest` (prediction freeze,
event start, sources with observation timestamps/content SHA256, odds flag false).
Only outcomes settled strictly before each freeze enter training. Simultaneous
freezes cannot learn each other's results. All fitting, preprocessing and
calibration belong inside the factory; use a fresh model on every call. Explicit
sports feature allowlists and authentic archived source payloads are required.
A timestamp assertion alone does not prove historical availability or authenticity.

The default comparator is a Beta-smoothed rolling sports-event frequency.
`elo_factory` adds a participant-strength baseline for binary winner markets.
For soccer 1X2 use separate one-v-rest assessments with appropriate baselines;
these binary metrics do not certify a normalized multiclass distribution.

Example Python API:

```python
from multisport.walk_forward import walk_forward, evaluate, snapshot
rows = walk_forward(events, factory, ['rating', 'availability'],
                    {'without_availability': ['availability']})
report = evaluate(rows, ['2024-25', '2025-26'], min_games=100,
                  required_ablations=['without_availability'])
```

Declare seasons, ablations, feature contract and thresholds before experiments.
`evaluate` emits paired per-season Brier, log loss and ten reliability bins for
plotting curves. It screens for improvement against baseline and all required
ablations in both losses in every holdout season, with minimum sample coverage.
A pass is neither statistical significance nor release approval: inspect reliability,
season dependence, uncertainty, source authenticity and selection bias independently.
No automatic promotion is permitted. Missing evidence fails the screen.

Before attaching outcomes, persist each forecast with `snapshot(record, directory)`;
record needs event ID, version, manifest and probabilities. First-write-only identity
prevents overwriting an event/version, with content digest returned for archival.
Store code revision, training event IDs and data hashes in the record. Filesystem
snapshots require external access controls/archival to resist later deletion.
Replay snapshots remain retrospective and must not be labeled live pregame evidence.

Validation: `python3 -m unittest discover -s multisport/tests -v` (Python >=3.9;
CI uses 3.11). Tests are synthetic temporal/metric contracts, not performance evidence.
