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

## Calendar selection and automatic publication

The public `nhl-schedule.json` contains verified fixtures in Santiago dates from yesterday through seven days ahead. `node frontend/collect-nhl-schedule.mjs` fetches two official NHL schedule weeks, validates coverage and normalizes IDs, states and final scores. It uses no credentials and contains no predictions. Pages regenerates this file before upload, twice daily, and after successful main-branch NHL capture runs. Failed collection fails deployment rather than publishing an invented empty schedule.

Changing the date updates the agenda, pending count, run date and forecast panel. Forecasts from a different capture day are hidden; future probabilities appear only after that day's real workflow runs and Pages completes. The dispatcher still submits the selected calendar day unchanged and only supports full-slate runs today through +7. Missing calendars and days with no pending games disable the run action. The workflow_run publication checks success and the same repository/main branch, checks out trusted main, and never consumes triggering-run artifacts.

## Automated dated postmortem

`NHL — daily postmortem and learning log` runs at 12:15 and 18:15 UTC (09:15/15:15 in Santiago during the current UTC−3 period; local times shift with DST). GitHub cron may be delayed. Each run retries the previous seven Santiago dates. Manual dispatch accepts one past/present `day` for backfills; it never dispatches the prediction model.

The process verifies frozen hashes and timestamps, retains the earliest issuance per game/model/market, and checks final scoreboard/PBP labels through both existing reconstructors. Live games remain pending. Source errors are recorded and warned rather than scored. Temporary source regression never replaces a previously complete report; corrections that still contain verified finals create a new revision. Identical source/report inputs do not create duplicate revisions or extra observations.

- `reports/nhl/daily/<date>/revisions/<sha>/`: retained report, selected frozen forecasts, normalized official response payloads compressed with deterministic gzip, and learning observations. The source hashes identify canonical JSON content.
- `frontend/data/nhl-postmortems/<date>.json` plus `nhl-postmortem-latest.json`: latest public date reports and index.
- `nhl/learning/postmortems/<date>.json`: postgame labels and signals, quarantined for future chronological training. No automatic parameter changes, retraining or model promotion.

Successful main-branch postmortem runs trigger the existing Pages workflow. It checks repository/branch/success, checks out trusted main and never consumes artifacts from the triggering workflow. The report appears under NHL “Historial y resultados”. The legacy #219 aggregate audit remains available manually; its overlapping schedule is removed. Paired ML evaluation #242 remains separate.

Run locally with Python 3.9+: `python -m nhl.daily_postmortem --date 2026-11-01`. CI uses Python 3.11. Tests cover idempotence, pending→final retries, malformed sequences, cross-source mismatch, source outages, retained revisions, tampered/post-start forecasts, future dates and dates without forecasts.

### Ficha deportiva junto al pronóstico

Pages genera `nhl-match-context.json` con `python -m nhl.match_context` después del
calendario oficial. La actualización programada de Pages es cada hora (minuto 20
UTC, sin garantizar puntualidad de GitHub Actions). También se actualiza al publicar
una nueva captura. El navegador solicita la ficha sin caché al cargar la página;
para consultar cambios posteriores hay que recargarla. Más de 90 minutos se indica
como potencialmente desactualizado.

Horario: America/Santiago. Sede/ciudad y árbitros/jueces de línea: endpoints oficiales
NHL gamecenter `landing` y `right-rail`. Las líneas ofensivas/defensivas, lesionados y
descartados son observaciones de NHL.com; se requieren ambos equipos del encuentro,
fecha local coincidente y fecha de modificación válida. Un artículo del día anterior
nunca rellena el de mañana. Una lista vacía de lesiones publicada significa «ninguno
reportado»; una fuente ausente significa «por informar». No se deriva un arquero
titular del orden de nombres ni de estadísticas de temporada.

La ficha expone su propia hora de captura y fuente. Es contexto actualizado separado
de la hora del pronóstico: no cambia ni recalcula probabilidades históricas. No se
reconstruye una alineación pregame de encuentros ya iniciados mediante datos actuales.
El frontend exige coincidencia exacta de ID, equipos y hora de inicio; si faltan
fuentes, conserva la predicción y comunica la falta de contexto. El colector conserva
huellas de las respuestas usadas; el JSON público se genera durante la publicación,
no es un archivo de entrenamiento ni un registro histórico inmutable de alineaciones.

### Entradas deportivas prospectivas para entrenar y comparar módulos NHL

Antes de emitir los cinco mercados, el workflow conserva por ejecución:

- `nhl/learning/pregame/run-ID.json`: identidades NHL de las líneas proyectadas,
  lesiones y descartados; arquero observado por el proveedor y su estado; estadísticas
  previas del arquero (temporada/últimos cinco, con muestras y corte exclusivo).
- `run-ID.sources.json.gz`: artículo y ESPN originales, más las capturas normalizadas
  de plantillas, reconciliación y resumen de historial. Se incluyen huellas SHA-256.
  El historial de arqueros conserva métricas y huella del origen; todavía no conserva
  cada respuesta original de game-log. Las huellas no certifican por sí solas la hora.

La captura solo admite nombres completos sin ambigüedad, posiciones compatibles,
ambos equipos del encuentro y fecha de artículo coincidente. Un jugador repetido o
simultáneamente lesionado/descartado y alineado impide marcar las líneas completas.
Faltantes permanecen nulos: cero lesionados publicados no equivale a lista ausente.
El estado «confirmed» de ESPN permanece atribuido al proveedor, sin elevarlo a
confirmación independiente. Los encuentros iniciados al congelar se excluyen.

La hora del vector es posterior a todas las capturas y anterior a la emisión de
pronósticos. Vincular con el baseline por run-ID y game-ID, comprobando además
`feature_as_of_utc <= prediction_as_of_utc < start_utc`; nunca imputar estas
observaciones a una emisión anterior del mismo encuentro. El post mortem proporciona
las etiquetas posteriores en otro registro, sin modificar la captura pregame.

Este primer paso construye la evidencia para la comparación, no activa un nuevo
predictor. `model_eligible`, `training_ready` y `probabilities_modified` permanecen
falsos y el efecto aplicado es nulo. No hay rating de lesión/línea supuesto ni pesos
manuales. Próxima etapa: dataset cronológico unido a resultados, política única de
emisiones, entrenamiento/validación/holdout, candidato de arquero primero y ablaciones
separadas de bajas y unidades. Comparar siempre con el baseline fuerte en la misma
cohorte, con calibración e incertidumbre. No promover solo por reunir un número fijo
de partidos o por un workflow verde.

### Cohorte y evaluación prospectiva del arquero

El post mortem reconstruye automáticamente `nhl/learning/goalie-cohort.json` mediante
`python -m nhl.goalie_prospective_evaluation --output nhl/learning/goalie-cohort.json`.
Verifica las huellas del paquete deportivo, sus fuentes y el baseline de la misma
emisión; solo admite `feature_as_of <= prediction_as_of < start`. Selecciona la
primera emisión elegible por partido, no la mejor. Los resultados oficiales se leen
del post mortem con huella de revisión verificada; los resultados ausentes permanecen
pendientes. Las exclusiones y emisiones repetidas se cuentan explícitamente. Esta
cohorte deportiva es distinta de la selección original del post mortem principal.

El primer experimento exige identidad y estado confirmado POR EL PROVEEDOR en ambos
arqueros. No lo convierte en confirmación independiente. Usa saves/shots de temporada
previos y conserva los tiros como cobertura. Por ahora no mezcla lesiones ni líneas.

La evaluación es manual y exige tres fechas explícitas previamente acordadas:

```sh
python -m nhl.goalie_prospective_evaluation --repo . --output /tmp/goalie-evaluation.json \
  --fit-through YYYY-MM-DD --validation-through YYYY-MM-DD --test-through YYYY-MM-DD
```

La salida manual es de creación exclusiva. No escribir sobre una evaluación anterior.
El programa no certifica que los cortes se hayan decidido antes de ver el holdout;
conservar el protocolo revisado antes del experimento. El workflow automático solo
actualiza la cohorte: nunca ajusta modelos a los resultados de la última jornada.

Se comparan tres brazos sobre los mismos juegos: baseline publicado; recalibración
de su logit; recalibración más diferencia de SV% local/visitante. La regularización
se selecciona únicamente por log loss de validación entre 0.005/0.02/0.1. Los
coeficientes usan exclusivamente entrenamiento. Las etiquetas de entrenamiento y
validación deben estar disponibles antes de las respectivas emisiones posteriores.
Los mínimos operativos son 400/50/100 juegos y al menos dos fechas por tramo; son un
control para no ajustar muestras diminutas, no un certificado de potencia/validez.
Sin cobertura, la salida informa insuficiencia y no contiene modelo ajustado.

La comparación conserva métricas Brier binario/log loss, calibración por deciles,
predicciones de holdout y diferencias emparejadas del candidato frente a ambos
controles. Los intervalos usan 1.000 remuestreos por fecha con semilla fija; persiste
la dependencia entre equipos y el riesgo de inspecciones repetidas. No hay promoción
automática ni cambios en los pronósticos de PULSO.

### Inferencia ML experimental y comparación por emisión

`nhl.goalie_ml_inference` exporta parámetros de la evaluación prospectiva y ejecuta
el candidato usando el `run_id` exacto de la presentación. El workflow guarda cada
salida de creación exclusiva en `nhl/learning/goalie-predictions/run-ID.json` y copia
esa salida a `frontend/data/nhl-goalie-comparison-latest.json`. No modifica el ML del
baseline. Ningún candidato ML tiene que inventar probabilidades RT/+3/rescate para
poder ejecutarse.

Modelo compatible ausente/inválido, variables faltantes, captura/artefacto posterior
a la emisión y encuentros iniciados producen «no ejecutado», probabilidad/delta
nulos y motivos específicos. El artefacto debe haber estado disponible antes del
pronóstico baseline comparado. Un artefacto válido calcula las dos probabilidades
complementarias ML, el control recalibrado y las diferencias en puntos porcentuales.
La diferencia frente al baseline incluye recalibración; la comparación con el
control la distingue, sin afirmar causalidad del arquero.

Se requieren las dimensiones exactas de coeficientes, medias y escalas; no se permite
el truncamiento silencioso de variables. Los parámetros se cargan del archivo
revisado `nhl/models/goalie-ml-candidate.json`; todavía no existe un artefacto real
compatible en esa ruta. Ver su README y el informe de compatibilidad de #269.

### Corrección de conexiones antes de ampliar los 13 módulos

El puente deportivo acepta el `nhl_game_id` que realmente emite el crosswalk y
rechaza alias de ID contradictorios. El workflow fija un corte de análisis posterior
a los historiales (con microsegundos), sin alterar las horas originales de captura.
`nhl.sporting_packages` conecta conteos reales de atajadas/tiros y muestras al módulo
cuantitativo; no inventa paquetes CRS, PP/PK ni disponibilidad. La identidad del
arquero se corrobora contra el plantel oficial, sin afirmar titularidad independiente.
El núcleo conserva la hora de captura y la hora de análisis por separado.

La matriz #258 incorpora ambos arqueros publicados en el artículo NHL.com cuando
fecha/equipos/IDs coinciden. Un plantel completo no se usa para adivinar candidatos.
La consulta #260 obtiene historial para todos los IDs de la matriz. La inferencia ML
conserva cada cruce local×visitante con nombre, resultado condicional o causa concreta
de bloqueo. No mezcla ni pondera los cruces suponiendo quién jugará. Historial ausente
en un arquero bloquea solo sus cruces. Candidatos no resueltos quedan listados.

Estos cambios reparan conectividad, cobertura y tiempo. No equivalen a 13 efectos
ajustados ni instalan un artefacto numérico compatible. El modelo conjunto, CRS,
unidades, equipos especiales y mercados derivados mantienen sus bloqueos explícitos
hasta disponer de fuentes, parámetros y evaluación. El baseline no se reemplaza.

### PP/PK y contexto de calendario con fuentes fechadas

Antes de establecer `SPORTING_ANALYSIS_AS_OF`, el workflow captura forma de equipo,
contexto de calendario y conteos oficiales PP/PK. `nhl.special_teams_capture` consulta
los reportes NHL Stats powerplay/penaltykill con temporada/fase regular/gameDate
explícitos; exige igualdad de cobertura por equipo y valida denominadores. Confirma
antes que el día de corte esté terminado mediante el score API. Si no lo está, o si
la fuente es inválida, deja el bloque indisponible. Se conservan cuerpos originales
comprimidos, fuentes, hashes y horas de recuperación.

`nhl.sporting_packages` incorpora los conteos reales al gate cuantitativo existente.
Una tasa suavizada de ese gate es un indicador observado, no un coeficiente ML
ajustado. El PR no crea un efecto probabilístico PP/PK.

`nhl.schedule_context` verifica cada encuentro contra el calendario oficial de ambos
equipos y conserva partido anterior, intervalo entre horas de inicio, B2B según fechas
oficiales y cambio de recinto. No afirma conocer descanso desde el final ni rutas o
kilómetros de viaje. Un partido previo sin jugar tiene estado planificado, y no se
trata como carga observada. El core verifica su disponibilidad antes del corte y
registra la observación; mantiene bloqueado el efecto hasta que se ajuste/evalúe.
