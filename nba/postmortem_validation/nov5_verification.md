# November 5 follow-up verification

Base audited: `1951c0c` (GitHub main, PR #341). Desktop dirty files for other
sports were not copied, committed or overwritten. Existing NBA postmortem
components were extended; no duplicate prediction engine was introduced.

Environment: Python 3.9.13 with repository requests dependency.

- Baseline: `python -m unittest discover -s nba/tests -q`: 329 tests passed.
- Updated: same NBA suite: 334 tests passed.
- `git diff --check`: passed.

Coverage includes two-sided roster/usage conservation, material-data PASS,
injury/replacement sensitivity, forced and committed turnover effects,
opponent residual arithmetic, fatigue/previous overtime/rotation load,
first-passage +20 versus final margin, distinct two-sided +20 events,
create-only sealed snapshots, no backdated emissions, frozen chronological
paired metrics, missing paths and tamper/market-input rejection.

The November 5 regression uses reported scores/context plus explicitly synthetic
witness paths; it does not manufacture possession exports. No prospective
probabilities were recovered. Zero eligible real-game predictions for these two
cases; hits, DUAL, Brier and log loss remain unknown. The suite is calculation and
regression verification, not a multi-season walk-forward performance result.

Remaining limits: verified player on/off, minute/load and possession exports;
external pretip publication proof; broad opponent coverage; fitted coefficients,
independent holdout and calibration. Existing Official baseline is preserved,
Challenger V2 remains research, all final selections PASS. No odds are inputs.
No merge or model promotion is authorized.
