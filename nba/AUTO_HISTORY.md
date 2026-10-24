# PR #37 — NBA verified automatic history

This action reconstructs three completed regular seasons from ESPN, cleans known cup final and exhibition contamination, and checks 1230 standard regular-season games in each. It additionally ingests 2026–27 completed regular-season games **only through the preceding UTC calendar day**, using the earlier of the prediction day and the present day's cutoff. This is conservative: excludes valid same-day finished games rather than risking result leakage. ESPN classifications and source reliability still require operational monitoring.

GitHub Actions > **NBA automatic verified-history pregame** > Run workflow > input US NBA game date. That run automatically rebuilds the history, fetches future fixtures using the pregame pipeline and records Elo, Challenger and hybrid candidate probabilities in a unique run artifact.

**Not yet unattended:** A manual action trigger is required. There is no daily cron, permanent database, automated settlement or email notification; artifacts expire after 90 days. A successful PR check runs unit tests, not the dispatch-only 3-year network ingestion. Only claim data is current after the real dispatch succeeds. Predictions remain uncalibrated candidates without lineup/injury adjustments.

The historical source is ESPN scoreboard and must be used in accordance with source terms. Game day is ESPN/US scoreboard date, not Santiago calendar date.
