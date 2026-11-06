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
