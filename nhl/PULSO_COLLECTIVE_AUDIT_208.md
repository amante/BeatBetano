# PR #208 — NHL collective uncertainty, reliability and ledger

Based on the exact #207 outcome-only NHL 2,811-game archive and frozen chronological 554-game holdout. Separate per-market one-vs-rest probability deciles and paired game bootstrap CI for challenger minus baseline Brier and Log Loss; deterministic seed 208. A confidence interval encompassing zero means the observed improvement is not established.

Ablation is limited to global historical outcome frequencies versus team-role historical frequencies. Player/goalie/CRS/PP-PK as-of historical covariates remain unavailable. No assertion of a full multi-module NHL model.

The frozen prospective ledger validator requires source and issue timestamps strictly before the fixture start, ordered timestamps, explicit verified source flag, odds-exclusion and normalized probabilities. SHA-256 is a content fingerprint, **not** proof that evidence actually existed then or that an immutable database was written.

**Remaining caveat:** simple paired bootstrap resamples games and ignores intergame temporal and team dependence. Prospective ledger storage, snapshots and true block/bootstrap confidence should precede model promotion.

Workflow: `PULSO NHL #208 — uncertainty calibration and ledger audit`. PR validates tests; manual dispatch on main performs historical real-data audit.
