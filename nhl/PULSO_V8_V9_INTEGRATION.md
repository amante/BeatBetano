# PULSO NHL v8/v9 — research simulation and publication contract

**This is a guarded integration slice, not a fully operational automated daily prediction service.** Official pregame ML/RT/+3 remain unavailable until validated sources and calibrated team-level model exist.

## Components

- `nhl/pulso_collective_v8.py`: fixture identity and strictly pre-start roster, goalie and scoring evidence gates. Rejects missing/ambiguous skaters, missing goalie confirmation and unverified CRS, units, goalie, PP/PK, context, rivalry evidence.
- Reuses `nhl.goal_process.calculate`: explicitly **unfitted** independent-Poisson research 60-minute goal process, with illustrative 50/50 OT ML, both sides' +3 lead and first-to-+3. Provided goal rates are **externally sourced inputs**; this PR does not fit them or turn verified module flags into causal coefficients.
- `frontend/pulso-nhl-status.js`: renders only the research status from optional static `frontend/data/pulso-nhl-research.json`. No file means "predicción no disponible". No fabricated scores or automated betting picks.

## CLI (research only)

`python -m nhl.pulso_collective_v8 --fixture fixture.json --snapshot pregame_snapshot.json --goalies goalie_observations.json --evidence verified_evidence.json --out frontend/data/pulso-nhl-research.json`

Do **not** publish arbitrary manually authored "verified" evidence. All source URL, immutable capture time, actual roster and official goalie confirmation must be independently checked and frozen prospectively. The required data feeds and learned team-level rate model are not yet implemented. This output never populates the official `predictions.json` feed or the score tracker; a research simulation cannot count as an actual prediction.

GitHub Pages is static and cannot POST simulations itself; the existing disabled endpoint remains disabled until a secure backend is deployed.

### Promotion gate

To offer real pregame predictions, separately implement (1) automatic as-of roster/goalie/injury capture and source integrity verification, (2) calibrated mappings from CRS/units/player projections/goalie/PP-PK/rivalry to team goal rates, (3) point-in-time walk-forward outcome validation, (4) scheduled immutable publication to Pages. None are falsely declared complete by this PR.
