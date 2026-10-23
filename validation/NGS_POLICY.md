# NFL Next Gen Stats historical integration — Phase 1

Official NFL Next Gen Stats (NGS) weekly datasets are distributed via nflverse:
`https://github.com/nflverse/nflverse-data/releases/download/nextgen_stats/ngs_{passing,receiving,rushing}.parquet`.
Sources: https://nflreadr.nflverse.com/reference/load_nextgen_stats.html and
https://nflreadr.nflverse.com/articles/dictionary_nextgen_stats.html.

The pipeline downloads 2016–2025 NGS *player/week* data, excludes season aggregates `week=0`, and computes lagged per-player within-season averages that exclude the current week's NGS measurement. No missing weeks are filled with future data. NGS publication time (typically overnight after games) must still be checked when preparing exact real-world pregame predictions; week ordering alone is a conservative initial gate.

**NGS is not NFL defensive tracking access.** Public nflverse NGS passing/receiving/rushing data do not disclose CB1/CB2/nickel coverage responsibility or all press/man/zone tracking assignments.

**No predictive lift is claimed yet.** This PR audits availability and features only. To fit an EPA + NGS challenger, choose a point-in-time game/team/player linkage, training seasons and paired 2024–25 test games. When NGS is absent due to participation thresholds, missing means unknown; do not infer zeros. Respect source data permissions and do not publish raw licensed data in the repo.
