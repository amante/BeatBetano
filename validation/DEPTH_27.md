# Availability Delta 2.7 — timestamped NFL depth charts

The nflverse depth-chart feed changed source and schema in 2025. From 2025 forward, records have an ISO8601 `dt` capture timestamp and position slot/rank. The CLI downloads and audits 2025 charts and selects each team's most recent snapshot strictly *before kickoff*. It outputs candidate player/position/rank records and coverage — **not confirmed starting lineups, injuries, active rosters, or CB1 vs CB2 vs nickel coverage assignments**.

The old 2023–2024 chart feed has a weekly index without an auditable collection timestamp; it cannot establish a reliable point-in-time candidate record by itself. Do not join postgame snap participation to infer the pregame starter. Depth slot/rank must not be mapped mechanically to CB1 or nickel in the official model.

NFL schedule `gametime` is interpreted in US Eastern local time. No effects on ML/spread/receiver props are fitted or promoted in this change. Historical completeness, identity quality and timing still require inspection.

Sources:
- https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html
- https://nflreadr.nflverse.com/articles/dictionary_depth_charts.html
