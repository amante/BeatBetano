# NHL secure run button — deployment guide

GitHub Pages cannot host an authenticated execution API. This backend **must be deployed separately** before the public run button is enabled. Do not put GitHub tokens in GitHub Pages, frontend JS, or public JSON.

## Deploy Cloudflare Worker

1. Create a Cloudflare Worker using `backend/nhl-dispatch-worker.mjs` as its module entrypoint and assign an HTTPS domain (example: `https://run.example.com`).
2. Protect route `/api/nhl/run` with **Cloudflare Zero Trust Access**, limiting access to authorized maintainers. The Worker additionally verifies the signed Access JWT against the published Access JWKS. Keep POST protected. Enable **Bypass OPTIONS requests** in the Access application CORS settings so unauthenticated browser preflights reach the Worker. This bypass applies only to OPTIONS; never bypass POST or disable JWT verification. The Worker answers preflight only for the exact allowed origin, POST and Content-Type.
3. Configure **non-secret** Worker environment variables:
   - `ACCESS_TEAM_DOMAIN`: `https://YOURTEAM.cloudflareaccess.com` (exact JWT issuer).
   - `ACCESS_AUD`: Cloudflare Access application AUD tag.
   - `ALLOWED_ORIGIN`: `https://amante.github.io`.
4. Configure Worker **secret** `GITHUB_TOKEN`: a short-lived or regularly rotated fine-grained GitHub token with **Actions: write** for **amante/BeatBetano only**. Restrict to authorized repository administrators. GitHub App installation credentials are preferable for production.
5. Test an authenticated `POST /api/nhl/run` from the PULSO origin using `{"sport":"nhl","date":"YYYY-MM-DD","scope":"all","event_ids":["2026020227"]}`; HTTP 202 means the dispatch was accepted, not that the workflow finished.
6. The public `frontend/data/runtime-config.json` now points to the deployed Worker:
   ```json
   {"simulation_endpoint":"https://pulso-nhl-runner.alexis-mante.workers.dev/api/nhl/run","simulation_endpoint_origin":"https://pulso-nhl-runner.alexis-mante.workers.dev"}
   ```
   These URLs are PUBLIC and must never contain credentials.
7. Verify the public website (NHL panel) submits only the full schedule and subsequently read the public `nhl-daily-predictions-latest.json`. The GitHub workflow itself captures the full official slate, independent of the browser's event ID list.

## Guardrails

- Merging publishes the public endpoint configuration through Pages. Worker source changes require a separate Cloudflare deployment; Pages does not deploy the Worker or configure Access.
- No tokens, API keys, GitHub PATs, or Cloudflare secrets are stored in `frontend/`.
- Explicit authenticated access, JWT verification, CORS origin allowlist, strict workflow allowlist, no arbitrary refs or parameters. Only full-day NHL, today through seven days in America/Santiago; no selected-only simulations.
- CSRF is constrained via origin check and JSON-only requests; deploy edge rate limiting and Cloudflare Access policies to prevent repeated dispatch.
- This launches the existing **experimental** model, not the unvalidated complete sporting/goalie-conditional engine.
- Each successful dispatch produces a new GitHub Actions run; the page does not yet display live job status, only acknowledgement.

## Authentication and real acceptance test

1. Deploy the updated Worker module separately, preserving existing variables and the GitHub secret. No Cloudflare deployment workflow or credentials are added by this change.
2. Confirm ALLOWED_ORIGIN is exactly `https://amante.github.io` (no repository path or trailing slash). Enable the OPTIONS bypass described above. Reference: https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/cors/
3. Open the Worker `/api/nhl/run` URL in a normal browser tab and complete Access login. A GET then returns 405, which is expected and does not dispatch anything. A Cloudflare dashboard login alone is not an Access application session.
4. Return to PULSO NHL and select today (Santiago) with pending games, scope “Todos los partidos”. Press Ejecutar once. Browser network tools should show OPTIONS 204, POST 202 and JSON `accepted: true`; check the Actions link for the new run and its requested day, then its final status and published output. A 202 only acknowledges dispatch.
5. If Access redirects, login expires, or the browser blocks cross-site cookies, the frontend offers the login link and does not retry automatically. Login does not override third-party-cookie restrictions. Check browser settings for these two sites or use the existing authenticated GitHub Actions interface as fallback. Do not put service tokens into browser code.

The selected calendar date is passed unchanged as the NHL schedule day (`inputs.day`); it is not a UTC timestamp conversion. The existing workflow captures the entire official NHL slate for that day, regardless of the browser event ID list. Its scheduled/blank-input UTC default is unchanged. Games displayed in Santiago may differ at calendar boundaries from the official NHL slate; selected-only runs remain unsupported.

Local tests mock JWKS and GitHub using a generated RSA key. They do not prove the deployed Access policy, cookie delivery, stored secret permissions, or production workflow success. A real authenticated POST and final Actions run must be checked separately; do not infer them from an unauthenticated preflight. No secrets are required for local tests.

Run with Node 22: `node --test backend/tests/*.test.mjs frontend/tests/*.test.cjs`. CI also runs the existing Python frontend suite with Python 3.11.
