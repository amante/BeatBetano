# Five-sport delivery contract (2026–27)

The same evidence, validation, and publication lifecycle should serve NBA,
NFL, NHL, tennis and soccer. Sport-specific data extraction and sporting
models remain separate. Current repository implementation only contains NBA.

### One integrated release per sport

1. Source fixtures / teams / players / time-stamped injury and lineup evidence.
2. Produce full eligible pregame slate and frozen sports-only baseline.
3. Run independent experimental challenger when data/model really exist.
4. Validate holdout performance chronologically (walk-forward, Brier/log loss,
   reliability, leakage, ablation). No automatic approval from code tests.
5. Publish one final result only when verified and independently validated.
6. Track outcomes and perform next-day post-mortem.

### Sport-specific modules to deliver

- **NBA:** player availability, five-man lineups, rotation/minutes, matchup impacts.
- **NFL:** active/inactive, snap shares, OL, CB1/CB2/nickel, coverage schemes,
  weather, defensive returns, game management, validated props.
- **NHL:** confirmed/probable goalies, replacement quality, top-six / D-pairing,
  power play, goalie-specific variance, divisional rivalry registry.
- **Tennis:** CTL, tournament adaptation, post-retirement recovery, surface-H2H,
  fatigue and best-of-three/five contexts.
- **Soccer:** xG adjusted to opponents, squad/defensive-unit integrity,
  draw risk, availability, tactical mismatch, explicit P(home/draw/away).

Model outputs must never be initialized using bookmaker odds.
`multisport.contract` is a shared structural validation only; it is not
a calibrated five-sport model, live data source or fixture completeness check.
