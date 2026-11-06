# NBA source capture and feature readiness

This is the data-connection phase following PR #338. No probability coefficients
or production approval rules change. Python 3.9+ is required. Install
`requests>=2.28,<3` and `pypdf>=5,<7` for source capture and PDF re-extraction.

## Commands

```sh
python nba/verifiable_capture.py --date 2026-11-06 \
  --history /path/to/validated-history.json \
  --official-report-url https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-06_07_45AM.pdf \
  --output /path/to/new-capture
python nba/source_readiness.py --capture /path/to/new-capture \
  --output /path/to/new-readiness.json
python -m unittest discover -s nba/tests -v
```

Select an already published PDF from the official NBA season report page; do not
guess a future report URL. Each capture uses a new directory. An empty history
list captures only the selected day and previous day's completed fixtures; it
does not establish multi-season coverage. All network requests have timeouts and
source failures remain visible. No access restrictions are bypassed.

The capture connects ESPN schedules/rosters/player and team boxscores, the existing
lineup source cascade and the official NBA injury PDF. It retains only sporting
fields from summaries, not betting markets. The manifest records source bytes;
the audit verifies required files, payload hashes, fixture binding, duplicate
identities and source timing. It re-extracts the official PDF instead of trusting
cached parsed rows. Manifest hashes establish integrity, not source accuracy.

Official tables can continue a date, matchup and team across page breaks. The
new opt-in parsing mode retains that context only when every page has an identical
report header and the initial page has a table heading. Default parsing retains
the original no-cross-page behavior. A new explicit matchup without a team resets
team context; missing or conflicting headers reject document continuity.

## Observed capture, November 6

The create-only capture at 13:04 UTC contains nine future games, 18 team rosters,
313 roster members, 18 projected starting fives and zero confirmed starting fives.
Its original cached parser found 71 injury rows but matched only 16 because context
was lost across pages. Re-extraction with document continuity finds 89 rows and
matches 84 claims to unique roster identities; five claims remain unmatched.
Unlisted roster members (229) stay unknown, not implicitly available. The raw
capture is unchanged; the derived readiness report documents the corrected counts.

Two previous-day games contain 53 player boxscore rows and reconciled scoring
paths. These produce observed maximum-lead targets, not normalized possession
endings. Capture time is after those games: none of these observations may be
presented as pregame injuries or forecasts for those historical fixtures.

## Remaining model inputs

Every fixture remains PASS. The readiness report lists blockers for each side:
complete active status, ID-bound confirmed starters, projected minutes/usage,
opponent-adjusted player on/off, replacement roles/quality, normalized possession
endings and independent holdout validation. Historical minutes are observations;
they are never substituted for projected minutes. Projected starter names cannot
be promoted to confirmed player IDs. Scoring paths cannot be substituted for
possession sequences. The capture does not manufacture any of these features or
attach arbitrary effects to named players.

The existing postmortem engine continues accepting its separately verified
feature contract. This raw capture is intentionally not labelled model-ready:
connecting it directly would silently invent critical inputs. Next ingestion
work requires a verified possession export and dated adjusted player effects,
followed by chronological prospective evaluation.
