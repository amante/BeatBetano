"""Transparent NBA player rotation, minutes and efficiency coverage.

Historical completed-game minutes are a provisional role estimate, NOT confirmed
pregame starters. A missing possession or scoring input remains null.
"""
import argparse,json,statistics
from pathlib import Path

def build(snapshot,history,player_sample):
 games_by_id={str(g["game_id"]):g for g in history}
 if len(games_by_id)!=len(history):raise ValueError("Duplicate historical game ids")
 players=player_sample.get("players",[])
 if not isinstance(players,list):raise ValueError("Invalid player sample")
 result={}
 for g in snapshot["predictions"]:
  tip=g["tipoff_utc"]
  teams={}
  for team in (g["home_team"],g["away_team"]):
   by_player={}
   for p in players:
    if p.get("team")!=team:continue
    event=games_by_id.get(str(p.get("game_id")))
    if not event or event["tipoff_utc"]>=tip:continue
    minute=p.get("minutes_played")
    if p.get("did_not_play") or type(minute) not in (int,float) or not 0<=minute<=65:continue
    pid=str(p.get("player_id") or "")
    if not pid:continue
    data=by_player.setdefault(pid,{"player_id":pid,"player":p.get("player"),"minutes":[],"games":[]})
    data["minutes"].append((event["tipoff_utc"],float(minute)));data["games"].append(event["game_id"])
   rotation=[]
   for data in by_player.values():
    vals=[value for _,value in sorted(data["minutes"])]
    # Require multiple observations before exposing any minutes estimate.
    projected=round(statistics.mean(vals[-5:]),1) if len(vals)>=3 else None
    rotation.append({"player_id":data["player_id"],"player":data["player"],
      "minutes_projection":projected,"sample_games":len(vals),
      "availability_verified":False,"starter_confirmed":False,
      "role":"provisional_rotation_candidate","projection_method":"mean_last_5_observed_minutes" if projected is not None else None})
   rotation.sort(key=lambda x:(x["minutes_projection"] is None,-(x["minutes_projection"] or 0),x["player_id"]))
   covered=sum(x["minutes_projection"] is not None for x in rotation)
   teams[team]={"sampled_players":len(rotation),"players_with_minutes_estimates":covered,"players_below_minimum_sample":len(rotation)-covered,
    "confirmed_starters":[],"starters_confirmation":"unavailable",
    "provisional_rotation":rotation,"confirmed_bench":[],
    "offensive_rating":None,"defensive_rating":None,"net_rating":None,
    "estimated_possessions":None,"points_per_possession":None,
    "scoring_possession_rate_pct":None,
    "efficiency_status":"unavailable_requires_verified_FGA_FTA_ORB_TOV_points_or_possession_feed",
    "minutes_status":"historical_estimate_not_availability_adjusted"}
  result[str(g["game_id"])]={"away_team":g["away_team"],"home_team":g["home_team"],
   "tipoff_utc":tip,"teams":teams,"current_starters_confirmed":False,
   "sporting_probabilities_adjusted":False}
 return {"snapshot_sha256":snapshot["content_sha256"],"games":result,
  "source":"historical ESPN completed-game minutes (sample), not lineup confirmation",
  "no_odds_input":True,
  "note":"Projection is historical sample average, not minutes guaranteed in today's lineup. ORtg/DRtg, possessions and percentage of scoring possessions are null until underlying statistics are available and verified."}

def markdown(data):
 out=["## NBA | Rotation, minutes and efficiency coverage","",
 "**No verified starting fives. Player minutes below are provisional historical estimates, not confirmed roles.**",""]
 for gid,g in data["games"].items():
  out.extend([f'### {g["away_team"]} @ {g["home_team"]} ({gid})',""])
  for team,info in g["teams"].items():
   out.append(f'**{team}** — historical player sample: {info["sampled_players"]}; minute estimates: {info["players_with_minutes_estimates"]}; insufficient sample: {info["players_below_minimum_sample"]}. Confirmed starters/bench: unavailable.')
   out.append("Player | Estimated minutes | Historical sample | Status")
   out.append("---|---:|---:|---")
   for p in info["provisional_rotation"][:12]:
    val="—" if p["minutes_projection"] is None else str(p["minutes_projection"])
    out.append(f'{p["player"]} | {val} | {p["sample_games"]} | provisional')
   out.append("ORtg: —; DRtg: —; possessions: —; points/possession: —; scoring-possession %: —.")
   out.append("")
 out.append("Unavailable values remain blank rather than fabricated; injury reports and quintets are not independently verified.")
 return "\n".join(out)+"\n"
def main():
 p=argparse.ArgumentParser()
 for k in ("snapshot","history","players","output","summary"):p.add_argument("--"+k,required=True)
 a=p.parse_args()
 x=build(json.loads(Path(a.snapshot).read_text()),json.loads(Path(a.history).read_text()),
         json.loads(Path(a.players).read_text()))
 for file,body in ((a.output,json.dumps(x,indent=2)),(a.summary,markdown(x))):
  path=Path(file);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
 print(json.dumps({"games":len(x["games"]),"confirmed_starters":0}))
if __name__=="__main__":main()
