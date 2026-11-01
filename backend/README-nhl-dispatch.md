# NHL secure run button — deployment guide

GitHub Pages cannot host an authenticated execution API. This backend **must be deployed separately** before the public run button is enabled. Do not put GitHub tokens in GitHub Pages, frontend JS, or public JSON.

## Deploy Cloudflare Worker

1. Create a Cloudflare Worker using `backend/nhl-dispatch-worker.mjs` as its module entrypoint and assign an HTTPS domain (example: `https://run.example.com`).
2. Protect route `/api/nhl/run` with **Cloudflare Zero Trust Access**, limiting access to authorized maintainers. The Worker additionally verifies the signed Access JWT against the published Access JWKS. Ensure Access policy covers *all* methods, including CORS OPTIONS if required, and permit your frontend origin.
3. Configure **non-secret** Worker environment variables:
   - `ACCESS_TEAM_DOMAIN`: `https://YOURTEAM.cloudflareaccess.com` (exact JWT issuer).
   - `ACCESS_AUD`: Cloudflare Access application AUD tag.
   - `ALLOWED_ORIGIN`: `https://amante.github.io`.
4. Configure Worker **secret** `GITHUB_TOKEN`: a short-lived or regularly rotated fine-grained GitHub token with **Actions: write** for **amante/BeatBetano only**. Restrict to authorized repository administrators. GitHub App installation credentials are preferable for production.
5. Test an authenticated `POST /api/nhl/run` from the PULSO origin using `{"sport":"nhl","date":"YYYY-MM-DD","scope":"all","event_ids":["2026020227"]}`; HTTP 202 means the dispatch was accepted, not that the workflow finished.
6. **Only after backend access, CORS and permissions work**, publish `frontend/data/runtime-config.json` with:
   ```json
   {"simulation_endpoint":"https://run.example.com/api/nhl/run","simulation_endpoint_origin":"https://run.example.com"}
   ```
   These URLs are PUBLIC and must never contain credentials.
7. Verify the public website (NHL panel) submits only the full schedule and subsequently read the public `nhl-daily-predictions-latest.json`. The GitHub workflow itself captures the full official slate, independent of the browser's event ID list.

## Guardrails

- No backend provisioned or active configuration in this PR. Until provisioned, the button deliberately reports unavailable and the Github Actions link remains available.
- No tokens, API keys, GitHub PATs, or Cloudflare secrets are stored in `frontend/`.
- Explicit authenticated access, JWT verification, CORS origin allowlist, strict workflow allowlist, no arbitrary refs or parameters. Only full-day NHL, today through seven days UTC; no selected-only simulations.
- CSRF is constrained via origin check and JSON-only requests; deploy edge rate limiting and Cloudflare Access policies to prevent repeated dispatch.
- This launches the existing **experimental** model, not the unvalidated complete sporting/goalie-conditional engine.
- Each successful dispatch produces a new GitHub Actions run; the page does not yet display live job status, only acknowledgement.
