# NBA Sporting Data — first live acquisition stage

The integrated-model workflow now **attempts** a live ESPN injury-feed request for every future game in the snapshot. Extracted player status, team, detail, source URL and retrieval timestamp are archived. A separate official NBA report reference is included: https://official.nba.com/nba-injury-report-2026-27-season/.

These observations are *supplementary*: ESPN does not establish the official NBA report, and response schemas may differ. Failures preserve the statistical snapshot and mark missing source information; they never masquerade as verified injury reports. This is stage one of ingestion. There is still **no verified starting five, injury cross-check, rotation-minute forecast, matchup analysis, or independently calibrated impact coefficient**. Consequently the integrated model will have `integrated_p_home=null` and picks cannot be approved. Obtain a reliable source and independently validate the availability-to-win probability mapping before activating adjusted probabilities.

Neither lineup projections nor betting odds are used as fabricated data. NFL unchanged.
