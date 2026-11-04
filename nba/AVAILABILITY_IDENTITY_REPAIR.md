# NBA availability: source-shape and identity repair

The November 4 original archive remains unchanged. A new observation at
2026-11-04T21:47:41Z (18:47:41 Chile), before all 13 tipoffs, is preserved in
`reports/nba-availability-2026-11-04-2147/` with a SHA-256 manifest.

## Cause and change

The current ESPN injuries response groups records using `id` and `displayName`,
with franchise identity under `injury.athlete.team`. The old reader expected
`group.team.abbreviation`, silently losing all current rows. The adapter now
accepts both shapes, rejects conflicting group/athlete IDs or abbreviations,
and preserves report time, source abbreviation and athlete ID when supplied.

An explicit alias map joins WAS/WSH, SAS/SA, NOP/NO, UTA/UTAH, NYK/NY and GSW/GS.
Output retains the fixture's team code. RotoWire fixture matching now uses the
same exact equivalences in both BeautifulSoup and standard-library paths.
No fuzzy franchise matching is performed.

Player claims use a roster-verified provider ID when present, otherwise a unique
normalized full name within the matching team. A mismatched explicit player ID
never falls back to a name. Future report timestamps are not used. Probable is
uncertain in the roster resolver, not confirmed active. Missing mentions remain
unknown. Source designation and original status remain in the archived evidence.

## Actual new capture

- 13 games, 26 teams, 452 current roster members.
- 81 matched supplementary injury claims: 64 Out, 17 uncertain.
- No unmatched player claims or conflicting player statuses in this capture.
- 26 teams with attributed projected/confirmed provider quintets, compared with
  20 in the earlier archive. This reflects a later observation as well as alias
  repair; it is not a controlled measurement of alias repair alone.
- 371 players have no explicit individual availability observation.
- Zero teams qualify for a full minutes allocation. No probability adjustment,
  official injury certification or complete sporting-model forecast is produced.

The official index's earlier HTTP 403 remains unresolved. ESPN is a usable
supplementary source, not a substitute for independently verified NBA game-day
availability. Provider quintets do not confirm the entire active bench.

## Reproduce

```
python -m unittest discover -s nba/tests -v
python nba/capture_availability.py \
  --snapshot reports/nba-2026-11-04/snapshot.json \
  --output-dir /tmp/nba-availability-new
```

The collector requires an intact snapshot and a cohort still entirely pregame.
It creates a new directory exclusively, stamps the new evidence, and never
rewrites the original snapshot or assigns today's observations to its earlier
freeze. Its `snapshot_sha256` fields identify the fixture cohort; the sidecar
summary explicitly records the later collection time and statistical snapshot
reference. New evidence must be used in a separately frozen future model run,
not retroactively passed as original-snapshot evidence.

Offline tests replay the new roster/status join and check all captured hashes.
A minimal sanitized real ESPN response is also retained as a parser regression
fixture, alongside synthetic conflicts, aliases, stale/future IDs and probable
status tests. Tests do not establish the truth of a provider's medical report.
