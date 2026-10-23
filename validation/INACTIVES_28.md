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
