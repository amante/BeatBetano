# NFL.com operational capture — Availability Delta 3.0

The new `nflcom_capture.py` script fetches a **public NFL.com injury-report HTML page** over HTTPS, with a strict official-domain allowlist, fails closed on HTTP rejection, and records the UTC retrieval timestamp plus SHA-256 of raw HTML. It deliberately does not bypass restrictions or claim to extract player statuses from dynamic markup. NFL.com may deny automated access; that is a reportable blocking condition, not a reason to bypass controls.

Example for a currently accessible published report:

```
python validation/nflcom_capture.py --url https://www.nfl.com/injuries/league/2026/REG7 --output results/nflcom_latest
```

Raw HTML captured *after* a historic match cannot be used as pregame evidence for that match. Preserve exact URL and retrieval time. There is no automatic retroactive history.

`nfl_player_identity.py` generates candidate GSIS matches from a **team-filtered roster with gsis_id, display_name, team**; even unique name candidates require review. For source ID mappings, nflverse provides `https://github.com/nflverse/nflverse-data/releases/download/players/players.csv`, but its release is a current reference database, not a historically frozen roster. Use a season-specific roster to establish team membership, and review possible name collisions.

No unattended scraping, new odds inputs, unverified CB1/CB2/nickel roles or predictive model promotion is introduced.
