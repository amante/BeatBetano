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

### Comparación ML con arquero

Cada tarjeta NHL distingue «Probabilidad base» de «Comparación con arquero». El
widget lee `data/nhl-goalie-comparison-latest.json` sin caché y exige el mismo
run-ID, fecha, equipos, inicio y probabilidad base que la presentación publicada.
Comprueba normalización de probabilidades, coherencia de deltas y cronología antes
de mostrar números. Una comparación de otra emisión nunca se reutiliza.

Si existe candidato ejecutado, muestra base/con arquero/diferencia para ambos
equipos y detalla la comparación adicional frente al control recalibrado. Solo ML:
no extrapola ese delta a RT/+3. Si falta el modelo, faltan variables o no hay una
comparación verificable, muestra «Modelo con arquero no ejecutado» con la causa.
No transforma la ausencia de cálculo en una probabilidad o delta de cero.

Este frontend admite el contrato del PR de inferencia ML; puede publicarse antes,
pero no habrá cifras de candidato hasta que el backend genere una salida compatible.
El PR de inferencia tampoco incorpora por sí solo parámetros NHL ajustados: el
artefacto debe entrenarse/evaluarse y revisarse con su contrato antes de activarlo.

La comparación también conserva **todos los cruces de arqueros potenciales** del
PR #294. Con dos candidatos resueltos por lado son cuatro escenarios, cada uno con
nombres, porcentajes o bloqueo específico. No se muestra solo el candidato que el
proveedor prefiera; no se calcula una media suponiendo probabilidades de titularidad.
La matriz debe ser el producto completo de sus IDs únicos. Los nombres pendientes
de identidad se conservan como advertencias, sin inventar un jugador o una proyección.

## Predicciones iniciales y actualizaciones

El dashboard comparte un panel de pronósticos para los cinco deportes, filtrado
por deporte y fecha de Chile. Presenta primera probabilidad, última, cambio en
puntos porcentuales, horas reales de emisión y todas las corridas disponibles.
Los supuestos, pendientes y versión del modelo se pueden desplegar. El selector
superior de pronósticos se sincroniza con la fecha de la agenda. Los datos de
fútbol conservan local/empate/visitante; no se fabrica un empate desde ML.

`build_forecast_index.py` deriva `frontend/data/forecast-index.json` del archivo
sellado `frontend/data/forecast_archive`. Verifica digests, cadenas por evento,
identidad, orden de cortes y emisiones pregame reales antes de publicar los campos
permitidos. No publica outputs crudos, no recalcula probabilidades y no promueve
selecciones. Una cadena inválida se excluye y se cuenta como incidencia; jamás se
rescata una versión antigua para presentarla como la última válida.

El despliegue Pages genera el índice desde main. También escucha la finalización
de los flujos diarios nuevos, porque los commits del bot no disparan por sí solos
un nuevo workflow de push. Conserva las condiciones que impiden desplegar PRs o
corridas externas. Los paneles históricos y de mercados especializados existentes
permanecen separados; las nuevas cifras son el historial del baseline disponible,
no una certificación del modelo completo ni nuevos cálculos +20/3GLP.

Sin archivo/datos para una fecha se informa ausencia de pronósticos archivados,
no ausencia de partidos. Si el índice no puede cargarse o no valida, se muestra un
error sin porcentajes. Se marca como historial cuando el partido ya comenzó y se
avisa si un partido futuro lleva más de ocho horas sin nueva emisión.

```sh
python frontend/build_forecast_index.py --archive /path/to/forecast_archive \
  --output /path/to/preview/data/forecast-index.json
node --test frontend/tests/progressive-forecasts.test.cjs
python -m unittest discover -s frontend/tests -v
```

La revisión visual local utilizó las dos corridas reales del piloto 6/11:
12 eventos indexados, 7 NBA para el día chileno 6/11, 2 NBA para 7/11 y 3 NHL
para 6/11. Estos datos de prueba no se copian automáticamente al archivo de
producción ni se presentan como recién recalculados. Hace falta el historial
real publicado por los flujos diarios (y la corrección de persistencia de #346).
