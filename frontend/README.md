# BeatBetano — Sports Intelligence Frontend

## Navigation
- `index.html`: public landing and login dialog UI.
- The real login button is intentionally disabled until an identity provider/backend is configured; no passwords are collected or stored.
- `Explorar demo sin cuenta`: opens a five-card sport selector (NBA, NFL, NHL, Soccer, Tennis).
- Each sport card navigates to `dashboard.html?sport=...`, preserving the original analytics screen, filtered by sport.
- Demo browsing is **not** authentication or access control. Protect backend routes before exposing private data.


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

## Public deployment

On merge into `main`, `.github/workflows/pages-deploy.yml` validates and
deploys the `frontend/` folder using GitHub Actions.

Expected public URL after successful deployment:
https://amante.github.io/BeatBetano/

If the first run fails at `Configure GitHub Pages`, repository administrators
must open **Settings → Pages → Build and deployment → Source → GitHub Actions**.
Then rerun the workflow from **Actions → Deploy BeatBetano frontend to GitHub Pages**.
The URL is not live until GitHub reports a successful deployment.

**Security:** This is an openly accessible static preview; the login form
is disabled and `Explorar demo sin cuenta` does not authenticate visitors.
Never publish secrets, account data, personal records, private predictions or
private API tokens under `frontend/` or `frontend/data/`. Every file in that
folder is publicly downloadable. Connect a proper identity provider and
authorization-enforcing backend before enabling real login.

The daily fixture updater commits publicly accessible JSON snapshots, not
private model training datasets. Empty historical prediction counters indicate
missing verified, settled predictions, not zero predictive accuracy.

## Sport isolation and simulation UX

A sport card opens `dashboard.html?sport=nba|nfl|nhl|soccer|tennis`.
The page is read-only and displays only the chosen sport, including cumulative
performance, yesterday's results and today's fixtures. Soccer fixtures retain
country/league grouping. No user upload controls are present.

Simulation requires an explicit **all upcoming games** or **selected upcoming
games** choice. The client sends a POST with `sport`, `date`, `scope` and
`event_ids` only to an optional same-origin HTTPS endpoint specified by
`frontend/data/runtime-config.json` as `simulation_endpoint`. That endpoint
must implement authentication, authorization, source collection, time-frozen
prediction and job execution. GitHub Pages is static and does **not** provide
that API. If no backend is configured, the button explicitly reports that no
simulation was executed; it never fabricates a result or calls a public
unauthenticated GitHub action. Public pages cannot protect restricted sports
models or private source data.
