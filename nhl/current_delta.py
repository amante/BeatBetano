"""Current NHL season incremental snapshots, without re-fetching prior seasons.

NHL Stats season endpoints return season-to-date totals, not change events.
We fetch three current-season reports only, compare against the prior cached
snapshot, and persist a new snapshot and a row-level delta. The cache is
best-effort; the run reports baseline_missing if restoration fails.
"""
import argparse, json, time
from datetime import date, datetime, timezone
from pathlib import Path
import requests
from multiseason_stats import API, REPORTS, extract, seasons

def identity(report, row):
    if report.startswith(("skater/", "goalie/")):
        player = row.get("playerId")
        team = row.get("teamId", row.get("teamAbbrevs", row.get("teamAbbrev")))
        if player is None: raise ValueError("Missing playerId")
        return json.dumps([player, team], sort_keys=True)
    team = row.get("teamId", row.get("teamAbbrevs", row.get("teamAbbrev")))
    if team is None: raise ValueError("Missing teamId")
    return json.dumps([team], sort_keys=True)

def index(report, rows):
    result = {}
    for row in rows:
        key = identity(report, row)
        if key in result:
            if result[key] != row:
                raise ValueError("Ambiguous duplicate identity in " + report + ": " + key)
            continue
        result[key] = row
    return result

def delta(previous, current):
    if previous and previous.get("season") != current["season"]:
        raise ValueError("Season mismatch; cannot compare snapshots")
    output = {"season": current["season"], "as_of_utc": current["as_of_utc"],
              "baseline_missing": not bool(previous), "reports": {}}
    for report in REPORTS:
        new = index(report, current["reports"][report])
        old = index(report, previous["reports"][report]) if previous else {}
        added = [new[k] for k in sorted(new.keys() - old.keys())]
        changed = [{"before": old[k], "after": new[k]} for k in sorted(new.keys() & old.keys()) if new[k] != old[k]]
        removed = [old[k] for k in sorted(old.keys() - new.keys())]
        output["reports"][report] = {"total":len(new), "added":added,
            "updated":changed, "missing_from_latest":removed,
            "added_count":len(added),"updated_count":len(changed),
            "missing_count":len(removed)}
    return output

def markdown(report):
    lines = ["## NHL current-season incremental data", "",
             "Only the active NHL season was queried. Historical seasons were not downloaded.",
             "**Baseline:** " + ("initial snapshot (no earlier cache)" if report["baseline_missing"] else "previous snapshot restored"), "",
             "| Report | Current rows | Added | Changed | Missing in latest |",
             "|---|---:|---:|---:|---:|"]
    for name, row in report["reports"].items():
        lines.append(f'| {name} | {row["total"]} | {row["added_count"]} | {row["updated_count"]} | {row["missing_count"]} |')
    lines += ["", "The source returns cumulative season totals; three current-season reports are refreshed, while the delta is computed locally.",
              "Missing from latest does not imply a trade, injury or departure without separate verification."]
    return "\n".join(lines) + "\n"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",default=date.today().isoformat())
    parser.add_argument("--previous",required=True)
    parser.add_argument("--snapshot",required=True)
    parser.add_argument("--delta",required=True)
    parser.add_argument("--summary",required=True)
    args=parser.parse_args()
    season=seasons(date.fromisoformat(args.date),1)[0]
    previous=None
    path=Path(args.previous)
    if path.exists():
        previous=json.loads(path.read_text())
    session=requests.Session()
    current={"sport":"nhl","season":season,"as_of_utc":datetime.now(timezone.utc).isoformat(),
             "source":API, "odds_used":False,"historical_backtest_eligible":False,
             "reports":{}}
    for report in REPORTS:
        current["reports"][report]=extract(lambda url:session.get(url,timeout=25),season,report)
        time.sleep(1.5)
    if not all(current["reports"][key] for key in REPORTS):
        raise RuntimeError("Incomplete NHL current season; refusing to replace cached snapshot")
    changes=delta(previous,current)
    for name,body in ((args.snapshot,json.dumps(current,indent=2)),
                      (args.delta,json.dumps(changes,indent=2)),
                      (args.summary,markdown(changes))):
        destination=Path(name);destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(body)
    print(json.dumps({"season":season,"baseline_missing":changes["baseline_missing"],
          "counts":{k:v["total"] for k,v in changes["reports"].items()}}))

if __name__=="__main__":
    main()
