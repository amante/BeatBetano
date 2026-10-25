# Official NBA injury PDF intake

NBA official 2026-27 injury index: https://official.nba.com/nba-injury-report-2026-27-season/ . The league updates this throughout the day. The pregame workflow attempts to retrieve its first linked NBA-hosted injury PDF and archive its source URL, SHA-256, download timestamp and extracted page text alongside the baseline predictions.

The archived PDF is **real official document evidence**, unlike ESPN secondary injury observations. However, this step intentionally does **not** certify individual injury status as-of a specific fixture: it does not validate the PDF's issue time relative to each game, normalize individual player/team rows, distinguish NOT YET SUBMITTED, or reconcile report updates. The output flags `individual_player_status_verified=false`, `source_report_as_of_utc=null`. Never treat source existence as confirmed availability or starting lineup. Errors from the upstream document do not produce fabricated verified fields or final probability.

Next: develop source-specific row extraction with fixture mapping, as-of snapshot checks and independent tests on actual report examples, followed by roster/source reconciliation and externally validated probabilistic impact. No betting odds. NFL untouched.
