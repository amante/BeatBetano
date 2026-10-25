# Complete NBA pregame contract

**A successful Elo/Challenger/Hybrid execution is not a completed pregame analysis.** This workflow generates only an odds-free statistical baseline.

A complete game review must verify **all seven** evidence stages with as-of timestamps, cited sources and game-specific details:
1. Starting five **both teams**, starter status versus projected, late scratches.
2. Official injury report, questionable/probable/out, game-time decisions and return limits.
3. Depth chart, bench quality, rotations and expected minutes (including replacement impact).
4. Positional matchups including primary defensive assignments, schemes and pace.
5. Current adjusted team form, individual contribution and opponent quality.
6. Schedule context: rest, back-to-back, travel, venue.
7. **Quantified and independently validated** net impact on win probability; uncertainty and model calibration.

Data must be timestamped **before tipoff** for a true pregame prediction. Final probabilities cannot be numerically adjusted by arbitrary injury guesses. Until a validated impact estimation and human-auditable source-backed ingestion mechanism exists, `final_p_home` is null and betting picks are never approved. A complete evidence checklist alone cannot promote a result to a calibrated probability.

The automatic history workflow now attaches `full_pregame_status.json` alongside the frozen statistical snapshot. It intentionally reports incomplete review if no evidence is fed. The snapshot SHA-256 remains immutable. This stage is a **fail-closed quality gate**, not a claim that injuries or starting lineups are currently ingested.

Every game in a full-day slate must pass identical checks. No bookmaker odds are features. NFL files untouched.
