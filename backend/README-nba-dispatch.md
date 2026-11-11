# PULSO NBA — protected Worker dispatch

The NBA button uses the existing Cloudflare Worker at `/api/nba/run`. The Worker accepts a same-origin, Cloudflare Access authenticated request and dispatches the repository's `Five-sport daily fixtures and results` workflow on `main`. The workflow captures the NBA slate and discovers the latest official NBA injury PDF automatically when no optional PDF URL is supplied.

## Cloudflare configuration

- Reuse the existing non-secret Worker variables `ACCESS_TEAM_DOMAIN`, `ACCESS_AUD`, and `ALLOWED_ORIGIN`. Set `ALLOWED_ORIGIN` exactly to `https://amante.github.io`.
- Keep `GITHUB_TOKEN` as a Cloudflare Worker secret with Actions write access scoped to `amante/BeatBetano`. Never put it in PULSO or runtime config.
- Protect `/api/nba/run` with the same Cloudflare Access identity policy as `/api/nhl/run`. If the current Access application matches only the NHL path, add the NBA path while preserving its login policy. Permit the CORS `OPTIONS` preflight as described in the existing dispatch README.
- Deploy the updated `backend/nhl-dispatch-worker.mjs` source to the existing Worker after the PR is merged. The repository does not deploy Worker code automatically.

The NBA route accepts only `{ "sport": "nba", "date": "YYYY-MM-DD" }` (date optional; it must be today's America/Santiago date). It returns HTTP 202 only after GitHub accepts the workflow dispatch; that response is not a completed forecast. Check the linked Actions workflow and the subsequent Pages deployment for completion.
