# Five-sport historical evidence standard

Applies to NBA, NHL, NFL, soccer and tennis. Every sport uses the same data-governance gates while retaining sport-specific collectors and targets.

1. Collect original game data from approved source connectors; record provenance and artifact ID. No uploads through the public frontend.
2. Keep raw completed-game source separately from schedules and live records.
3. Normalize unique event IDs, team/player participants, event dates and final results, rejecting duplicates, missing or nonfinite scores.
4. Check expected coverage against independently established season or competition schedules. Without a verified expected count, do not claim complete coverage.
5. Preserve SHA256 hashes, original source, canonical outcome ledger and audit manifest in an immutable tagged GitHub Release; an Actions artifact alone expires.
6. Separately reconstruct point-in-time pregame features, train and run chronological holdouts. Historical scores and completed-game boxscores are NOT pregame evidence.

## NBA

The existing NBA three-season backtest workflow now audits exactly 3,690 completed regular-season games and retains the cleaned original historical JSON in its artifact.
After a successful run, use Actions > Multisport — Historical audit and archive with sport=nba, source_run_id=<run ID>, source_artifact=nba-three-season-backtest, source_json_path=results/nba/three_seasons.json, expected_games=3690 and persist_release=true.
Verify the GitHub release history-nba-source-<run ID> and integrity manifest. The path inside the downloaded artifact must match; inspect its tree if GitHub changes directory structure.

## NHL

Continue using the richer, existing official NHL gamecenter and PBP 2,811-game validator and immutable-release workflow. The generic schema check does not supersede goal-sequence verification.

## NFL, soccer and tennis

Collector-specific history extraction and valid expected schedules remain necessary. Soccer adds country, league and draw targets; tennis requires tour, surface, retired/walkover handling; NFL requires ties and overtime handling. Do not call these fully covered until the extractors and coverage gates actually run.

## Guardrails

Every generic audit manifest explicitly says point_in_time_pregame_features_verified=false, calibration_completed=false and official_model_promoted=false.
GitHub Releases are public in this repository: never include secrets, private data or feeds you lack rights to redistribute.
End users never import prediction files to the website; only the source-driven backend pipelines can populate model outputs.