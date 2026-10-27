"""Reconcile automatic goalie roster candidates into match-ready *observations*.

Multiple candidates per team are retained. No starter is inferred or win
probability adjusted. This step bridges NHL goalie_feed and goalie_daily.
"""
import argparse,json
from pathlib import Path
from goalie_daily import assess

def integrate(slate,captured):
    if slate.get("sport")!="nhl" or captured.get("sport")!="nhl":
        raise ValueError("NHL documents required")
    if slate["as_of_utc"]!=captured["as_of_utc"]:
        raise ValueError("Mismatched freeze time")
    raw=captured.get("games",{})
    out={}
    for game in slate.get("events",[]):
        gid=str(game["event_id"]);entry=raw.get(gid,{})
        sides={}
        for side in ("home","away"):
            team=game[side+"_team"];candidates=entry.get(side,{}).get("candidates",[])
            if not isinstance(candidates,list):raise ValueError("Goalies must be a list")
            seen=set();measured=[];statuses={};rejected_stat_rows=0
            for c in candidates:
                pid=c.get("goalie_id")
                if not pid or pid in seen:raise ValueError("Missing/duplicate goalie ID")
                seen.add(pid)
                obs=assess(c,team,slate["as_of_utc"],game["start_utc"])
                label=c.get("data_status",obs.get("status","unknown"))
                statuses[label]=statuses.get(label,0)+1
                rejected_stat_rows+=c.get("rejected_stat_rows",0)
                if obs.get("status")=="measured_unfitted":
                    measured.append(obs)
            sides[side]={"team":team,"goalie_candidates":measured,
                "total_rostered_candidates":len(candidates),
                "capture_status_counts":statuses,"rejected_stat_rows":rejected_stat_rows,
                "starter_confirmed":False,"starter_id":None}
        out[gid]={"home":sides["home"],"away":sides["away"],
            "goalie_rating_delta":None,"win_probability_delta":None,
            "both_starters_confirmed":False,"validated":False}
    return {"sport":"nhl","schema_version":1,"as_of_utc":slate["as_of_utc"],
        "games":out,"no_odds_input":True,
        "note":"Measured SV% and workload for roster candidates; NOT confirmed starting goalies or calibrated impact."}

def summary(report):
    lines=["## NHL goalie capture coverage","",
           "Candidate roster entries do not imply confirmed starters. No ML/RT/+3 adjustments are authorized.","",
           "| Game ID | Team | Roster candidates | Measured candidates | Capture statuses | Rejected stat rows |",
           "|---|---|---:|---:|---|---:|"]
    for gid,game in report["games"].items():
        for side in ("home","away"):
            row=game[side]
            statuses=", ".join(f"{k}: {v}" for k,v in sorted(row["capture_status_counts"].items())) or "none"
            lines.append(f'| {gid} | {row["team"]} | {row["total_rostered_candidates"]} | {len(row["goalie_candidates"])} | {statuses} | {row["rejected_stat_rows"]} |')
    return "\\n".join(lines)+"\\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--slate",required=True);p.add_argument("--candidates",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--summary")
    args=p.parse_args()
    result=integrate(json.loads(Path(args.slate).read_text()),json.loads(Path(args.candidates).read_text()))
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2))
    if args.summary:
        Path(args.summary).write_text(summary(result))
    print(json.dumps({"games":len(result["games"]),
        "measured_goalies":sum(len(g[s]["goalie_candidates"]) for g in result["games"].values() for s in ("home","away"))}))
if __name__=="__main__":main()
