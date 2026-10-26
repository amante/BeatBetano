# NBA lineup cascade — source intake contract

Priority: NBA/club official **confirmed**, then reported confirmations; if no confirmation exists, RotoWire expected, ESPN projected, Propedia projected, or another properly attributed source. Confirmed reports require source-specific provenance and must never be mislabeled as league official.

Each provider adapter must emit records:
`{"game_id":"ESPN_EVENT_ID","team":"MIL","provider":"rotowire","status":"projected","starters":["... five names ..."],"source_url":"https://...","observed_at_utc":"2026-10-26T22:00:00Z"}`.

Run `python nba/lineup_source_cascade.py --snapshot snapshot.json --sources source_candidates.json --output lineup_cascade.json --summary lineup_cascade.md`.

**Current scope:** evidence selection, source trust, pretip cutoff, conflicts and report. Provider network scrapers/API integrations are **not implemented in this PR**. Neither a provider name nor a URL implies that actual candidates were fetched. RotoWire offers an authenticated `get-nba-lineups.php` API; use approved credentials/terms, not fabricated access. Public web pages may change or block automation. Do not use bookmaker odds as model input.

**Remaining:** provider adapters; fixture/team/player ID reconciliation; as-of timestamps and caching; pregame freshness rules; roster and availability matching; minute adjustments; chronological evaluations. No current starters are automatically confirmed from prior games.
