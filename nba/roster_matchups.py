"""Conservative NBA roster-depth and positional matchup evidence report.

No assumption that athlete lineup or matchup assignments are confirmed.
Builds per-game auditable status from optional human-verified game inputs and
supplementary injury observations. No numerical impact is fabricated.
"""
import argparse,json
from pathlib import Path
from datetime import datetime,timezone

def parse_time(value):
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset()!=timezone.utc.utcoffset(d):
        raise ValueError("Evidence requires UTC timestamp")
    return d

def evaluate(snapshot,sporting=None,verified=None):
    sporting=(sporting or {}).get("games",{})
    verified=(verified or {}).get("games",{})
    observed=parse_time(snapshot["created_at_utc"])
    outputs={}
    for pred in snapshot["predictions"]:
        gid=str(pred["game_id"]);tip=parse_time(pred["tipoff_utc"])
        x=verified.get(gid,{})
        team_reports={}
        for designation,team in (("home",pred["home_team"]),("away",pred["away_team"])):
            team_input=x.get(designation,{})
            five=team_input.get("confirmed_starters",[])
            bench=team_input.get("bench_rotation",[])
            injuries=team_input.get("official_injuries",[])
            recorded=team_input.get("source_observed_at_utc")
            timely=False
            if recorded:
                try:timely=parse_time(recorded)<=observed and parse_time(recorded)<tip
                except (TypeError,ValueError):pass
            starters_ok=(timely and team_input.get("lineup_confirmed") is True
                and len(five)==5 and len(set(five))==5 and all(isinstance(v,str) and v.strip() for v in five)
                and bool(team_input.get("lineup_source")))
            rotation_ok=(timely and starters_ok and team_input.get("rotation_verified") is True
                and isinstance(bench,list) and all(isinstance(i,dict) and i.get("player") and
                isinstance(i.get("expected_minutes"),(int,float)) and not isinstance(i.get("expected_minutes"),bool)
                and 0<=i["expected_minutes"]<=48 for i in bench) and bool(bench))
            injuries_ok=timely and team_input.get("official_injury_report_verified") is True and isinstance(injuries,list) and bool(team_input.get("injury_source"))
            team_reports[designation]={"team":team,"starter_count":len(five),"confirmed_starters":five if starters_ok else [],
              "lineup_verified":bool(starters_ok),"rotation_verified":bool(rotation_ok),
              "official_injury_report_verified":bool(injuries_ok),
              "official_injuries":injuries if injuries_ok else [],
              "bench_rotation":bench if rotation_ok else [],
              "source_observed_at_utc":recorded if timely else None}
        matchup=x.get("matchup",{})
        matchup_ok=(isinstance(matchup,dict) and matchup.get("verified") is True
          and bool(matchup.get("source")) and bool(matchup.get("source_observed_at_utc")))
        if matchup_ok:
            try:matchup_ok=parse_time(matchup["source_observed_at_utc"])<=observed and parse_time(matchup["source_observed_at_utc"])<tip
            except (TypeError,ValueError):matchup_ok=False
        complete=all(t["lineup_verified"] and t["rotation_verified"] and t["official_injury_report_verified"] for t in team_reports.values()) and matchup_ok
        outputs[gid]={"home":team_reports["home"],"away":team_reports["away"],
          "positional_matchups_verified":bool(matchup_ok),
          "matchup_description":matchup.get("notes") if matchup_ok else None,
          "supplementary_injuries":sporting.get(gid,{}).get("supplementary_injury_observations",{}),
          "availability_review_complete":bool(complete),
          "quantified_log_odds_adjustment":None,
          "status":"verified_inputs_unquantified" if complete else "requires_verified_roster_and_matchup_data"}
    return {"snapshot_sha256":snapshot["content_sha256"],"schema_version":1,"games":outputs,
      "no_official_probability_adjustment":True}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True);p.add_argument("--sporting-data")
    p.add_argument("--verified-data");p.add_argument("--output",required=True)
    a=p.parse_args()
    load=lambda f:json.loads(Path(f).read_text()) if f else {}
    r=evaluate(load(a.snapshot),load(a.sporting_data),load(a.verified_data))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x") as f:json.dump(r,f,indent=2)
    print(json.dumps({"games":len(r["games"]),
     "availability_complete":sum(g["availability_review_complete"] for g in r["games"].values())},indent=2))
