# Availability Delta 2.8 — point-in-time inactive bridge

This component joins 2025+ timestamped candidate depth charts to **independently collected** inactive snapshots. The minimum CSV schema is:

`game_id,team,gsis_id,inactive,observed_at_utc,kickoff_utc,source`

The `observed_at_utc` timestamp must be from the actual historical collection event, strictly before kickoff. Merely retrieving an archived final roster today does **not** prove what was available before kickoff. Unmatched rows are explicitly unknown, never healthy.

The public nflverse injury source stopped after 2024, and 2025 dated depth charts alone do not show game-day inactives. Sportradar describes a game-roster feed that reflects inactives around 90 minutes before kickoff, but it requires authorized API access and historical collection records, and is **not** automatically downloaded by this module.

Sources:
- https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html
- https://developer.sportradar.com/football/docs/nfl-ig-game-status-workflow
- https://developer.sportradar.com/football/reference/nfl-game-roster

This PR implements data validation, linking and coverage reporting only. No real 2025 historical inactive snapshots have been acquired, no CB1/CB2/nickel coverage responsibility is inferred, and no predictive improvement or ML/spread/prop change is claimed.

## Official NFL.com as corroborating source

Use NFL.com league injury reports (e.g. https://www.nfl.com/injuries/league/2025/REG6), official game-day inactives reports at nfl.com, and club-issued dated depth chart PDFs (often hosted on static.clubs.nfl.com). These can corroborate a player's published practice status, game designation or pregame inactive announcement.

**Critical timing rule:** retain publication/capture timestamp and exact source URL, verify announcement occurred before kickoff, and record the source's roster name and player ID mapping. The page as retrieved today does not itself prove what it said before a past kickoff. NFL.com injury statuses (Questionable/Doubtful/Out) are not the same as 90-minute official inactives; club *unofficial* depth charts are not confirmed starting lineup or CB1/CB2/nickel coverage responsibility. Comply with NFL.com terms and robots/access limits; do not silently scrape protected endpoints or fabricate missing records.

For 2025+, NFL.com is an official supplementary evidence source, while nflverse remains a reproducible statistics feed. Cross-source disagreements must be flagged for manual adjudication, not auto-imputed as healthy.
