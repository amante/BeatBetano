# NBA teammate-absence-conditioned weights (research stage)

The #108 estimator calculates an athlete's baseline minutes in independently verified historical games, compares minutes in games where specified teammates were **confirmed OUT**, and shrinks the observed difference toward baseline. It excludes games at or after forecast tipoff. Missing historical availability verification is not treated as a teammate being active.

The result is an **unvalidated opportunity weight**, not an authorized minutes prediction. It still needs a three-season chronological, team-specific historical active/out ledger, reconciliation of player-team changes, minimum sample tests, and an on-court position-compatible lineup optimizer. When evidence is insufficient the model returns `baseline_only_unvalidated_absence_effect` or `insufficient_baseline`, rather than inventing an uplift.

This isolated module does **not** wire into current NBA forecast production or replace the capped 240-minute scenario allocator. Integration should occur only after historical observation quality and walk-forward improvement are demonstrated. No bookmaker odds are used.

The same architecture generalizes to NFL targets/carries, NHL ice-time/shots, and soccer playing time, using sport-specific exposure and eligibility definitions.
