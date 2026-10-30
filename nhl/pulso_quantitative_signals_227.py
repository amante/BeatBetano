"""#227: evidence-gated quantitative CRS, goalie and PP/PK research signals.

Inputs are pregame verified source packages, not odds or inferred lineups.
Null is mandatory for missing/late/unattested signals; no official predictions.
"""
import argparse,json,math
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def valid_source(src,issued,start):
 if not isinstance(src,dict) or not src.get("source_url") or not src.get("as_of"):return False
 try:return parse_utc(src["as_of"])<=issued<start
 except (ValueError,TypeError):return False

def number(x):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):return None
 return float(x)

def beta(success,trials,alpha,beta_):
 s=number(success);n=number(trials)
 if s is None or n is None or s<0 or n<0 or s>n or n==0:return None
 return {"observed":s/n,"shrunk":(s+alpha)/(n+alpha+beta_),"sample":n}

def compute(bridge,packages):
 if bridge.get("kind")!="sporting_source_bridge":raise ValueError("Sporting bridge required")
 out={}
 for gid,g in bridge["games"].items():
  issued=parse_utc(g["as_of"]);start=parse_utc(g["start_utc"])
  if issued>=start:raise ValueError("Late fixture")
  pg=packages.get(gid,{})
  teams={}
  for team in (g["home"],g["away"]):
   inp=pg.get(team,{});values={};issues=[]
   crs=inp.get("crs",{})
   if valid_source(crs,issued,start) and crs.get("availability_independently_verified") is True and crs.get("lineup_identity_verified") is True:
    x=number(crs.get("offense_proxy"));d=number(crs.get("availability_delta"))
    if x is not None and d is not None:values["crs"]={"offense_proxy":x,"availability_delta":d}
   if "crs" not in values:issues.append("crs_not_verified")
   goalie=inp.get("goalie",{})
   if valid_source(goalie,issued,start) and goalie.get("goalie_player_id")==g["teams"][team].get("provider_goalie_id_observed") and goalie.get("identity_independently_verified") is True:
    saves=number(goalie.get("prior_saves"));shots=number(goalie.get("prior_shots"));games=number(goalie.get("prior_games"))
    if saves is not None and shots is not None and games is not None and games>=3 and shots>=50 and saves<=shots:
     values["goalie"]={"player_id":goalie["goalie_player_id"],"prior_games":int(games),
        "shrunk_save_pct":(saves+90.5)/(shots+100),"prior_save_pct":saves/shots}
   if "goalie" not in values:issues.append("goalie_history_not_verified")
   st=inp.get("special_teams",{})
   if valid_source(st,issued,start) and st.get("events_prior_to_capture") is True:
    pp=beta(st.get("powerplay_goals"),st.get("powerplay_opportunities"),2,8)
    pk=beta(st.get("opponent_powerplay_goals"),st.get("times_shorthanded"),2,8)
    if pp is not None and pk is not None:values["special_teams"]={"pp":pp,"opponent_pp_allowed":pk}
   if "special_teams" not in values:issues.append("special_teams_not_verified")
   teams[team]={"signals":values,"issues":issues,"sporting_ready":not issues}
  out[gid]={"game_id":gid,"home":g["home"],"away":g["away"],"as_of":g["as_of"],
   "teams":teams,"sporting_signals_complete":all(t["sporting_ready"] for t in teams.values()),
   "official_probabilities":None}
 return {"kind":"quantitative_sporting_signals_research","games":out,"official":False,
  "model_trained":False,"odds_used":False,
  "note":"Goalie shrinkage is saves/shots, not GSAx. Verified signals are not an official calibrated model."}

def main():
 p=argparse.ArgumentParser()
 for k in ("bridge","packages","out"):p.add_argument("--"+k,required=True)
 a=p.parse_args()
 result=compute(json.loads(Path(a.bridge).read_text()),json.loads(Path(a.packages).read_text()))
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({"fixtures":len(result["games"]),"complete":sum(g["sporting_signals_complete"] for g in result["games"].values())}))
if __name__=="__main__":main()
