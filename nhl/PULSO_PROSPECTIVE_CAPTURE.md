# PULSO NHL — prospective evidence collector

This is a genuine operational source-ingestion step. It retrieves the **NHL official schedule** and **ESPN provider goalie observations** before puck drop, preserves source time/hash/observations as a downloadable GitHub Actions artifact, and publishes only an unavailable/readiness status to the PULSO NHL page.

**This is not yet an automatic prediction engine.** An ESPN probable/confirmed status is a provider assertion, not a verified official starter. The collectors cannot reliably supply complete dated player availability, verified goalie identity for each team, or calibrated collective scoring rates. As a result, the published `probabilities` are null and the model isn't marked official.

Workflow: `PULSO NHL — prospective pregame source capture`. On merge it is scheduled twice daily and also supports manual run, day default current UTC date. Artifacts are retained 90 days; this is not long-term immutable history. No raw private information or sportsbook odds is used. Deployment of the updated status on Pages occurs via the existing frontend workflow.

Next implementation gates: (1) verified pregame expected-lineup identity crosswalk and injury evidence; (2) goalie confidence and evidence provenance; (3) actual player-to-team rate mapping and chronological calibrated collective model; (4) prospective shadow scoring. Do not promote automatic published results to ML/RT/+3 until gates pass.
