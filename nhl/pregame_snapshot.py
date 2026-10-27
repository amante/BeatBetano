"""Attach already captured NHL season evidence to a future pregame slate.

No additional NHL Stats requests, odds, or promoted calibrated ratings.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from delta_pillars import feature_sheet

def utc(value):
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("Timezone required")
    return d.astimezone(timezone.utc)

def join(slate,snapshot,max_age_hours=12):
    freeze=utc(slate["as_of_utc"]);captured=utc(snapshot["as_of_utc"])
    if slate.get("sport")!="nhl" or snapshot.get("sport")!="nhl":
        raise ValueError("NHL inputs required")
    if captured>freeze:raise ValueError("Snapshot from the future")
    age=(freeze-captured).total_seconds()/3600
    if age>max_age_hours:raise ValueError("Snapshot too stale for pregame")
    expected=f'{freeze.year-(freeze.month<7)}{freeze.year-(freeze.month<7)+1}'
    if snapshot.get("season")!=expected:raise ValueError("Wrong season")
    sheet=feature_sheet(snapshot)
    games=[]
    for game in slate.get("events",[]):
        if utc(game["start_utc"])<=freeze:raise ValueError("Already started game")
        home=game["home_team"];away=game["away_team"]
        if home not in sheet["teams"] or away not in sheet["teams"]:
            raise ValueError("Missing NHL team data: "+home+"/"+away)
        games.append({"event_id":game["event_id"],"start_utc":game["start_utc"],
          "home_team":home,"away_team":away,
          "home_evidence":sheet["teams"][home],"away_evidence":sheet["teams"][away],
          "official_ml":None,"challenger_ml":None,"regulation_probabilities":None,
          "three_goal_lead_probabilities":None,"first_to_plus_three":None,
          "ratings_calibrated":False})
    if not games:raise ValueError("No future NHL games; refusing empty success")
    return {"sport":"nhl","as_of_utc":slate["as_of_utc"],"snapshot_as_of_utc":snapshot["as_of_utc"],
       "snapshot_age_hours":round(age,3),"season":expected,"games":games,
       "odds_used":False,"calibrated":False,"reused_snapshot":True,
       "note":"Descriptive evidence only; player stats not confirmed game lines or starts."}

def markdown(data):
    lines=["## NHL today — cached current-season evidence","",
      f'Snapshot age: {data["snapshot_age_hours"]} hours; {len(data["games"])} future matchups.',
      "No historical download; no confirmed lineup or fitted probabilities.","",
      "| Away | Home | Skaters (A/H) | Goalies (A/H) | Source |",
      "|---|---|---:|---:|---|"]
    for x in data["games"]:
        a=x["away_evidence"];h=x["home_evidence"]
        sk=lambda z:z["unit_evidence"]["forwards"]["players_with_stats"]+z["unit_evidence"]["defense"]["players_with_stats"]
        lines.append(f'| {x["away_team"]} | {x["home_team"]} | {sk(a)}/{sk(h)} | {len(a["goalie_evidence"]["candidates"])}/{len(h["goalie_evidence"]["candidates"])} | NHL Stats |')
    return "\n".join(lines)+"\n"

def main():
    parser=argparse.ArgumentParser()
    for key in ("slate","snapshot","output","summary"):parser.add_argument("--"+key,required=True)
    args=parser.parse_args()
    result=join(json.loads(Path(args.slate).read_text()),json.loads(Path(args.snapshot).read_text()))
    for path,content in ((args.output,json.dumps(result,indent=2)),(args.summary,markdown(result))):
        dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content)
    print(json.dumps({"games":len(result["games"]),"snapshot_age_hours":result["snapshot_age_hours"]}))
if __name__=="__main__":main()
