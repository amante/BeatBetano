# PR #38 — NBA scheduled postmortem and early season diagnostic

The **NBA prospective daily postmortem** GitHub Action runs daily at 14:30 UTC, or manually with an optional pregame workflow run ID. It finds the latest successful **NBA automatic verified-history pregame** run on `main`, downloads the original immutable prospective snapshot, validates its content hash, fetches ESPN completed games around relevant UTC dates, and writes a **separate** result-only report with Brier scores for Elo, Challenger, and hybrid. Unfinished games remain explicitly unsettled.

This job **does not** create a pregame snapshot: the upstream workflow remains manually started. Scheduled postmortems will fail when no eligible snapshot exists and may repeatedly assess the same latest snapshot; use a durable artifact registry and snapshot date-indexing before claiming true unattended daily forecasting/postmortems. Snapshots and reports currently expire after 90 days.

A separate early-season experiment `nba/early_season.py` replaces the abrupt all-Elo fallback under three games with a **candidate** linear shrinkage based on the smaller team-specific sample (0–10 games). It is not wired into prediction selection and is NOT production-approved; freeze and prospectively evaluate before considering promotion.

No bookmakers' odds enter the model; no lineup or injury information is verified; no automatic postmortem is possible without a prior pregame snapshot. Do not treat exploratory candidate forecasts as approved betting recommendations. NFL untouched.
