# PULSO NHL #211 — NHL.com editorial lineups in daily source capture

Collect NHL.com published projected-lineup blocks in each prospective snapshot, alongside official roster identities, schedule and goalie crosswalk. Source observations are saved as an artifact even if they cannot be mapped to a particular fixture. HTML parsing or network failures are recorded explicitly and do not stop source-readiness capture.

**Crucially:** this integration does not assert a publication date, per-fixture applicability, complete player lineup, starter goalie confirmation or CRS eligibility. The existing `nhlcom_lineup_identity.resolve` requires separate independent fixture/date attestations; do not bypass it. No official pregame probabilities are published. Next stage is robust fixture/date source attestation and player identity coverage measurements, then controlled CRS integration.
