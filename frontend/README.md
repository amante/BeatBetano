# BeatBetano — Sports Intelligence Frontend

Static, responsive frontend for five sports. No npm dependencies or server.

## Run locally
```bash
python -m http.server 8080 --directory frontend
```
Then open http://localhost:8080.

## Importing data
Click **Importar reporte JSON** and select a report conforming to
`multisport.contract`, or an adapter report created by
`python -m multisport.sport_adapters --sport nhl --input source.json --output report.json`
(with the relevant sport and input).

The browser reads the file locally. It makes no requests to external
services and contains no fake matchups or probabilities.

Supported sports: `nba`, `nfl`, `nhl`, `soccer`, `tennis`.
Reports must contain `sport`, a timestamp, and an event array named
`events`, `games`, or `predictions`. Each event must identify its
two teams/participants and event ID.

The app intentionally displays `final_probability` **only** when the
report includes `all_inputs_verified: true`,
`independent_validation_passed: true`, and a nonempty
`validation_report_ref`. These declarations are not independent proof
of correctness; the source must be audited separately. No probabilities
are calculated by this UI.

## Scope
Research dashboard, not a production recommendation engine. Data imports
are held in in-memory browser state and are lost when the page reloads.
There is no login, connected storage, backend or deployment configured.
