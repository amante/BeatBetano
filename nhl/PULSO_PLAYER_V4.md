# PULSO PLAYER NHL v4 — independent multiteam validation

Use the GitHub Actions workflow **PULSO PLAYER — NHL v4 multiteam and probability validation** with `workflow_dispatch`, branch `main`, input `teams=EDM,COL,DAL,FLA,NYR,TOR` (or a smaller set if API throttles). Results appear as an artifact containing `metrics.json`, `dated_predictions.json`, and `provenance.json`.

- Four methods compete on the **same** dated player-games, requiring at least ten earlier appearances on the current team: historical mean, prior five games, prior ten games, contextual PULSO.
- For shots and goals, a provisional Poisson distribution transforms each expected count into `P(at least one)`; binary Brier score, log loss and observed/expected rates compare models. These are exploratory, **not calibrated probabilities**.
- Player-cluster bootstrap 95% intervals describe contextual-vs-historical MAE differences. Independent team-level replication is necessary.
- Results from a 6-team run must not be described as whole-league validation.
- This reuses the PULSO v3 roster discovery, schedule-derived rest, and NHL game-log sources. The source roster list is retrospective; this does **not** constitute point-in-time player availability, so it cannot yet publish production pregame ML/RT/3GLP or betting recommendations.
- Odds are never used. Every target game's player outcomes are excluded from its prior history. No statistics are synthesized.

**Scope note:** roster discovery uses historical rosters for the requested clubs but v3 only processes appearances with the requested team's schedule; transfers and teams not in the request remain out of scope. The selected NHL source endpoint shape and rate limits must be observed in the live run.
