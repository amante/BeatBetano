# Injury archive experiment (2023–24)

Source: nflverse public injury CSV releases, documented at https://nflreadr.nflverse.com/articles/dictionary_injuries.html. Its injury feed ends in 2024. Fields used: season, week, team, gsis_id, position, report_status, date_modified.

This ingestion **does not retroactively claim full point-in-time snapshots**. The archive may contain last-modified information only. Records modified after kickoff are excluded. Only actual records with timestamp <= kickoff are eligible. The 2023–24 sample is strictly a **coverage audit**, not a scientifically validated historical injury-effect estimate.

Game clock fields in nflverse schedules are interpreted as US Eastern time and converted to UTC. Verify schedule schema and timestamp semantics against actual downloaded files. A record's timestamp preceding kickoff is necessary, but not sufficient, to prove the archive captured every player; full-team coverage remains unverified. Do not interpret zero OUT counts as no injured players.

Out/IR/inactive labels use existing conservative position counts. CB alone does not establish CB1, CB2, or nickel assignment; injury status alone does not establish starter/replacement quality. No spread, ML or WR/TE prop effect is claimed. Any 2025/26 time point requires an independent audited source.
