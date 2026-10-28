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
