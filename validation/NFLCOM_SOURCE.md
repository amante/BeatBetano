# NFL.com evidence ingestion policy

Verified public page structure: [NFL injury report by week](https://www.nfl.com/injuries/league/2025/reg6) includes practice participation and **game status** (Out / Doubtful / Questionable). NFL.com official inactives are a different game-day announcement.

The validator ingests lawfully collected, point-in-time CSV evidence with: game_id, team, player_name, position, game_status, source_url, captured_at_utc, kickoff_utc. Captures must precede the actual kickoff; later web retrieval cannot retrospectively prove what a page said. Original capture archives should be retained with source provenance, capture clock, and permissions; this branch does not scrape live pages or manufacture historic snapshots.

NFL.com player names must be resolved to authoritative stable player IDs with explicit match review before joining to nflverse GSIS IDs. Never silently fuzzy-match two players with the same name. NFL.com injury-report Out is a game designation, not a confirmed 90-minute inactive or confirmed CB1/CB2/nickel assignment.

Use as a supplementary evidence feed alongside nflverse, not as a replacement for play-by-play statistics. No real historical NFL.com captures were supplied or ingested for training in this branch. No NFL model coefficients have changed.
