"""PULSO 253: descriptive, non-calibrated candidate goalie daily indicators.

Season and recent SV% are shrunk by observed shots; workload is described from
observed prior game dates. No invented confirmations, GSAx or win probability.
"""
import argparse,json
from datetime import date
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def evaluate(source,prior_strength=200,prior_sv=0.900):
 if source.get("kind")!="nhl_candidate_goalie_history_251" or source.get("official_predictions")!=0:
  raise ValueError("Wrong candidate evidence")
 if prior_strength<=0 or not 0<prior_sv<1:raise ValueError("Invalid reference")
 cutoff=parse_utc(source["as_of_utc"]).date()
 games=[]
 for game in source["games"]:
  teams={}
  for club,row in game["teams"].items():
   out={"nhl_player_id":row.get("nhl_player_id"),
     "starter_status":"not_independently_confirmed",
     "provider_status":row.get("source_goalie_status","unverified"),
     "goalie_daily_rating":None,"gsa_x":None,"ml_delta":None,
     "status":"blocked","blockers":[]}
   if row.get("status")!="observed":
    out["blockers"].append(row.get("reason",row.get("status","unknown")));teams[club]=out;continue
   data=row["metrics"];season=data["season_to_date"];recent=data["last_5_games"]
   shots=season["shots_against"];saves=season["saves"]
   if any(type(x) is not int or x<0 for x in (shots,saves)) or shots==0 or saves>shots:
    raise ValueError("Invalid observed save counts")
   last=data.get("last_game_date")
   days=(cutoff-date.fromisoformat(last)).days if last else None
   if days is not None and days<=0:raise ValueError("Postcutoff goalie appearance")
   # Stable prior is descriptive shrinkage; not an estimated NHL win coefficient.
   smoothed=(saves+prior_strength*prior_sv)/(shots+prior_strength)
   rshots=recent["shots_against"];rsaves=recent["saves"]
   if type(rshots) is not int or type(rsaves) is not int or not 0<=rsaves<=rshots:
    raise ValueError("Invalid recent save counts")
   out.update({"status":"descriptive_evidence_only",
     "season_sv_pct":round(saves/shots,6),
     "recent_5_sv_pct":round(rsaves/rshots,6) if rshots else None,
     "shrunk_sv_pct":round(smoothed,6),
     "season_shots_against":shots,"recent_5_shots_against":rshots,
     "season_games":season["games"],"recent_5_games":recent["games"],
     "days_since_last_appearance":days,
     "workload_fatigue_adjustment":None,
     "prior_strength_shots":prior_strength,"prior_reference_sv_pct":prior_sv})
   teams[club]=out
  games.append({"game_id":game["game_id"],"home":game["home"],"away":game["away"],"teams":teams})
 return {"kind":"nhl_goalie_descriptive_daily_253","as_of_utc":source["as_of_utc"],
  "games":games,"observed_sides":sum(t["status"]=="descriptive_evidence_only" for g in games for t in g["teams"].values()),
  "official_predictions":0,"odds_used":False,"calibrated":False,
  "limitations":["Reference SV% and shot prior are explicit descriptive constants, not trained coefficients.",
    "Last-five games do not establish rest-day workload without full recent appearance dates.",
    "No GSAx, starter confirmation, full Goalie Daily Rating, fatigue effect or ML/RT/+3 adjustment."]}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--history",required=True);p.add_argument("--out",required=True)
 a=p.parse_args();out=evaluate(json.loads(Path(a.history).read_text()))
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(out,indent=2))
 print(json.dumps({"observed_sides":out["observed_sides"],"official_predictions":0}))
if __name__=="__main__":main()
