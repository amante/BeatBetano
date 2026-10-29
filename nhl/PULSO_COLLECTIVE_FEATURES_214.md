# PULSO #214 — collective evidence integration boundary

Combines existing #213 skater CRS proxy, goalie historical evidence, prior-source Bayesian PP/PK and context/rest into a fixture-level evidence vector. Explicitly rejects mismatched game IDs, future issue time and late source timestamps.

**Not a trained multi-module NHL model:** goalie past save rate is not confirmed starter or causal goalie performance, the defensive unit rating and calibration remain absent. Missing fields remain null, and NO ML, RT, +3 or team goal rates are emitted. The unit proxy source in #213 needs point-in-time verified player/lineup availability to reach even research-complete status. Context must come from the already existing sourced NHL research context pipeline.

Next steps: build historical as-of feature ledger and train out-of-time team-rate model; validate against outcome-only baseline before deployment.
