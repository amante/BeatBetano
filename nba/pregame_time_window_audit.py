"""Identify NBA pregame opportunities lost while expensive history steps run."""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
def audit(scoreboard,now):
 current=datetime.fromisoformat(now.replace("Z","+00:00"))
 if current.tzinfo is None:raise ValueError("UTC timestamp required")
 captured=datetime.fromisoformat(scoreboard["as_of_utc"].replace("Z","+00:00"))
 rows=[]
 for g in scoreboard["future_fixtures"]:
  tip=datetime.fromisoformat(g["tipoff_utc"].replace("Z","+00:00"))
  rows.append({"game_id":g["game_id"],"away_team":g["away_team"],"home_team":g["home_team"],
   "tipoff_utc":g["tipoff_utc"],"eligible_when_captured":tip>captured,
   "still_pregame":tip>current,"crossed_tipoff_during_run":captured<tip<=current})
 return {"captured_at_utc":scoreboard["as_of_utc"],"checked_at_utc":current.isoformat(),
  "initial_pregame_games":len(rows),"crossed_tipoff":sum(x["crossed_tipoff_during_run"] for x in rows),
  "games":rows,"predictions_backdated":False}
def main():
 p=argparse.ArgumentParser()
 for key in ("scoreboard","output","summary"):p.add_argument("--"+key,required=True)
 a=p.parse_args();s=json.loads(Path(a.scoreboard).read_text())
 data=audit(s,datetime.now(timezone.utc).isoformat())
 for name,value in ((a.output,json.dumps(data,indent=2)),(a.summary,"## Pregame cutoff audit\n\n"+f'Captured: {data["initial_pregame_games"]}, crossed tipoff during execution: {data["crossed_tipoff"]}. No retroactive predictions.\n'):
  f=Path(name);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(value)
 print(json.dumps({"captured":data["initial_pregame_games"],"crossed_tipoff":data["crossed_tipoff"]}))
if __name__=="__main__":main()
