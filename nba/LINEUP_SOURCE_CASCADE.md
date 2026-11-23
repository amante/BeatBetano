# NBA lineup cascade — source intake contract

Priority: NBA/club official **confirmed**, then reported confirmations; if no confirmation exists, RotoWire expected, ESPN projected, Propedia projected, or another properly attributed source. Confirmed reports require source-specific provenance and must never be mislabeled as league official.

Each provider adapter must emit records:
`{"game_id":"ESPN_EVENT_ID","team":"MIL","provider":"rotowire","status":"projected","starters":["... five names ..."],"source_url":"https://...","observed_at_utc":"2026-10-26T22:00:00Z"}`.

Run `python nba/lineup_source_cascade.py --snapshot snapshot.json --sources source_candidates.json --output lineup_cascade.json --summary lineup_cascade.md`.

**Active source:** the public RotoWire NBA lineups page is fetched first for projected starting fives. NBA or team confirmed lineups override the projection; ESPN and other projected sources remain fallbacks. Every selected lineup retains its provider, URL, status and pregame timestamp. RotoWire projected starters are never described as official confirmation.

The capture reads only five names from each expected-lineup list. It does not infer active status from absence in the injury list. Odds and referee information are handled separately as display-only market context and never enter the model. If the page layout or fixture mapping prevents extraction, the capture reports zero lineup coverage instead of fabricating names.

**Remaining:** reconcile lineup names to the complete current roster; source and resolve RotoWire player availability claims without conflating them with official NBA injury statuses; track source freshness; and evaluate lineup accuracy prospectively.
