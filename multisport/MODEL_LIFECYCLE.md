# Shared model lifecycle — five sports

This layer is shared by NBA, NFL, NHL, soccer and tennis without
mixing their features, coefficients or historical data.

## Current scope
- `model_registry.py` validates model IDs, dataset SHA-256, Git code revision,
  training/feature cutoffs and declared certification.
- `data_lineage.py` verifies timestamped source manifests for pregame use,
  forbids bookmaker odds and rejects future observations.
- A separate CI workflow executes synthetic contract tests on modifications.
- Existing NBA, NFL and NHL production/research workflows are NOT changed.
- Soccer and tennis do not yet have sport-specific model implementations.
- An `independently_validated` attestation must be externally audited;
  passing this schema alone does not authorize deployment.
- No model is automatically promoted by this registry.

## Next integration
Sport adapters will write canonical evidence manifests and model records,
then expose paired baseline/challenger predictions. The validation engine
must verify actual held-out scores and underlying source provenance before
any promotion.

## Standard forecast procedure — all sports

NBA, NFL, NHL, soccer and tennis share this procedure; sport-specific features,
models, coefficients and calibration remain separate.

1. **Initial:** publish the available odds-free baseline using historical strength,
   expected participants/rotation and currently known availability. Confirmed
   starters and a complete final injury list are not prerequisites. Declare
   assumptions and unresolved inputs, including whether lineups are projected.
2. **Update:** rerun the relevant sport model as new facts arrive. Publish the
   probabilities actually produced, including unchanged probabilities; do not
   invent adjustments, injury penalties or scenario weights. Record changed
   assumptions and unresolved inputs with the revised forecast.
3. **Final pregame:** the latest pre-start run. “Final” describes timing, not
   complete information or certified calibration. Remaining uncertainty is still
   explicit. A further final-pregame run may supersede it before start.

Forecast publication and selection approval are separate. Missing confirmed
starters alone cannot erase a usable baseline. A forecast can coexist with PASS
for a selection. A baseline cannot fill an unsupported target: e.g. NBA ML does
not manufacture +20, and a two-way vector does not supply soccer's draw outcome.
If there is no source-model probability, report that fact without fabricating one.
A sport without an implemented model is not made operational by this protocol.

The shared `sport_adapters` now publishes a separate `forecast` object with stage,
model version, probabilities, assumptions and unresolved inputs for all five
sports. Soccer retains home/draw/away; the other existing contracts use two-way
outcomes. Source-model probability vectors can be supplied explicitly as
`forecast_probabilities`; the adapter also recognizes legacy NBA/NFL/NHL fields
and soccer Poisson vectors. Illustrative results retain an explicit illustrative
label. The legacy certified `final_probability` remains separate; updating a
stage never sets certification or approves a selection.

The CLI creates sealed, create-only snapshots using `forecast_revisions`, with
actual emission time distinct from input cutoff. Historical runs are labelled
retrospective replay. `--previous-snapshot` links revisions, preserves the initial
forecast, records before/after probabilities and assumptions, and checks fixture
identities and chronological cutoffs. It cannot overwrite an earlier snapshot.
Initial/update/final evaluations must be compared separately on paired fixtures;
never select the most favorable revision after seeing the outcome.

```sh
python -m multisport.sport_adapters --sport nba --input source.json \
  --stage initial --revision model-version --output initial.json
python -m multisport.sport_adapters --sport nba --input updated-source.json \
  --stage update --revision model-version --previous-snapshot initial.json \
  --output update.json
```

Use nfl, nhl, soccer or tennis with the same workflow and their own model outputs.
This change covers shared publication and revision history. Sport-specific
feature engines and their data requirements remain responsible for computing
updates; their missing enhanced estimates cannot suppress an available baseline
in this publication layer. Existing daily workflows must explicitly call this
adapter to emit the new staged artifacts; they are not silently rewritten here.

## Daily execution integration

The five-sport fixtures workflow now calls `multisport.daily_pipeline` on each
scheduled/manual run. It generates the existing NBA Elo/margin/rest baseline,
NFL historical Elo and NHL prior-day standings baseline through their actual
sport-specific daily commands. It also runs the existing soccer Poisson model
with the previously selected historical penalty, only for Premier League fixtures
whose team names map uniquely to its training identities. Its cache is keyed by
historical source hashes, penalty and model code. Other soccer leagues and tennis
report missing baselines explicitly; no new model is invented for them.

NBA extends the digest-verified historical ledger with cached prior-day scoreboard
deltas. NFL refreshes its nflverse ledger at most once per UTC day in the scheduled
runner. NHL uses the game's US league date, including a still-future UTC fixture
on the preceding league calendar date. Historical and confirmed-result controls
remain in their source models. Sources are acquired independently: a failure in
one sport is recorded without blocking another sport's initial forecast.

The NBA, NFL and NHL daily entrypoints publish their base immediately, before
optional enhanced evidence calculations. Their manual workflows use the same
archive as the scheduled five-sport workflow. Generation/persistence jobs share a
publication concurrency group and run only from main; tests are outside that
publication group. Archives are committed to `frontend/data/forecast_archive`
and also uploaded with source outputs. Forecast history is not an evictable cache.
`frontend/data/forecast_status.json` records requested coverage, source errors and
fixture IDs without a usable baseline; it does not label partial coverage complete.

`daily_forecasts` records one sealed chain per sport/provider event ID (safe hashed
folder). This allows started fixtures to leave the slate and new fixtures to join
without breaking other chains. It retains each model's original cutoff, model
output and output digest. Re-running identical source bytes/cutoff is idempotent;
changed outputs with the same cutoff are rejected. Each new cutoff appends a new
revision. An absent probability keeps previous files and reports the missing new
forecast; it never silently republishes the old number as newly calculated.

Stages are initial, update and final_pregame. The default final window is 30 minutes
before source-reported start and can be configured at publication. A final stage
is still provisional with unresolved inputs; it never approves a selection.
The existing twice-daily schedule remains in place; workflow_dispatch can refresh
between scheduled runs. This is not an automatic listener for every news update.
The dashboard rendering itself is not changed by this integration: staged outputs
and status are data artifacts, not certified final predictions.

```sh
python -m multisport.daily_pipeline --fixtures frontend/data/daily.json \
  --archive /path/to/persistent/forecast_archive --workdir /path/to/model-workdir \
  --summary /path/to/forecast_status.json
python nba/daily_pipeline.py --history history.json --date YYYY-MM-DD \
  --output new-baseline.json --forecast-archive /path/to/persistent/forecast_archive
```

NFL and NHL commands accept the same `--forecast-archive` option. Reuse the archive
on reruns and keep raw NBA baseline filenames new, because its existing raw-source
snapshots remain create-only. No market odds, validation certifications or sporting
selection gates are changed by running these publication commands.


## Módulos: creado, conectado y con efecto en probabilidades

PULSO mantiene un estado independiente por módulo y deporte:

1. **Creado:** existe una implementación ejecutable; una mención en la hoja de ruta no basta.
2. **Conectado:** la ejecución diaria incorpora su salida al paquete del pronóstico o a uno de sus mercados publicados. Recopilarla en un archivo aislado no basta.
3. **Afecta porcentajes:** la salida entra en la fórmula de su mercado y puede cambiar sus probabilidades.

Solo los módulos con las tres etapas pasan a seguimiento y calibración. Eso no significa que estén certificados. La tabla visible en PULSO etiqueta el alcance de candidatos experimentales por separado del pronóstico final. El inventario transversal está en `frontend/data/model-modules.json` y se valida en CI.
