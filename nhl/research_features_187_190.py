"""NHL research feature package #187–190.

Frozen previous-date game records only. Missing PP/PK, player availability,
travel and starter reports remain unknown; no inferred official lineup.
These are uncalibrated descriptive features, NOT ML/RT/3GLP boosts.
"""
from collections import defaultdict
from datetime import date
import math

DIVISIONS={"Atlantic":"BOS BUF DET FLA MTL OTT TBL TOR","Metropolitan":"CAR CBJ NJD NYI NYR PHI PIT WSH","Central":"CHI COL DAL MIN NSH STL UTA WPG","Pacific":"ANA CGY EDM LAK SEA SJS VAN VGK"}
DIV={t:k for k,v in DIVISIONS.items() for t in v.split()}
TIER_A={frozenset(x.split("-")) for x in ("BOS-MTL","BOS-TOR","EDM-CGY","PIT-PHI","PIT-WSH","NYR-NYI","NYR-NJD","TOR-OTT","LAK-ANA","VGK-SJS","FLA-TBL")}

def safe_rate(made,chances,alpha=2.,beta=8.):
 if chances is None or made is None:return None
 if not isinstance(chances,int) or not isinstance(made,int) or chances<0 or made<0 or made>chances:raise ValueError("Invalid special-teams counts")
 return {"opportunities":chances,"conversions":made,
  "raw":made/chances if chances else None,
  "posterior_mean":(made+alpha)/(chances+alpha+beta),
  "prior_alpha":alpha,"prior_beta":beta}

def compile_features(fixtures,game_observations):
 """game_observations are dated POSTGAME facts; target game is never inspected."""
 by_day=defaultdict(list)
 for game in fixtures:
  if game["home"]==game["away"]:raise ValueError("Invalid fixture")
  by_day[game["date"]].append(game)
 if len({g["game_id"] for g in fixtures})!=len(fixtures):raise ValueError("Duplicate fixture")
 seen={};prior_game={};recent=defaultdict(list);out=[]
 for day in sorted(by_day):
  current=date.fromisoformat(day)
  # freeze features for all games on this same date
  for g in by_day[day]:
   h,a=g["home"],g["away"];data={}
   for team in (h,a):
    past=prior_game.get(team)
    rest=(current-past).days-1 if past is not None else None
    last7=sum(0<(current-x).days<=7 for x in recent[team])
    totals=seen.get(team,{})
    data[team]={"rest_days":rest,"back_to_back":rest==0 if rest is not None else None,
     "games_last_7_days":last7,
     "pp":safe_rate(totals.get("pp_goals"),totals.get("pp_chances")) if totals else None,
     "pk_opponent_scoring":safe_rate(totals.get("pk_goals_allowed"),totals.get("pk_chances")) if totals else None}
   hrest,arest=data[h]["rest_days"],data[a]["rest_days"]
   division=DIV.get(h) is not None and DIV.get(h)==DIV.get(a)
   pair=frozenset((h,a))
   out.append({"game_id":g["game_id"],"date":day,"home":h,"away":a,"teams":data,
    "rest_differential":hrest-arest if hrest is not None and arest is not None else None,
    "division":division,"rivalry_tier":"A" if pair in TIER_A else None,
    "home_ice":True,"home_underdog":None,"travel_km":None,"referees":None,
    "special_teams_coverage":all(data[t]["pp"] is not None and data[t]["pk_opponent_scoring"] is not None for t in (h,a)),
    "source_class":"historical_prior_dates_only","not_an_official_probability":True})
  # apply today's results only AFTER every today's feature is frozen
  for g in by_day[day]:
   observation=game_observations.get(str(g["game_id"]))
   for team,side in ((g["home"],"home"),(g["away"],"away")):
    prior_game[team]=current;recent[team].append(current)
    if observation is None:continue
    node=observation.get(side)
    if node is None:continue
    values=seen.setdefault(team,{"pp_goals":0,"pp_chances":0,"pk_goals_allowed":0,"pk_chances":0})
    if any(node.get(k) is None for k in values):continue
    if any(not isinstance(node[k],int) or node[k]<0 for k in values):raise ValueError("Invalid historical ST data")
    if node["pp_goals"]>node["pp_chances"] or node["pk_goals_allowed"]>node["pk_chances"]:raise ValueError("Impossible ST data")
    for k in values:values[k]+=node[k]
 return out

def roster_delta(history,baseline,expected,as_of):
 try:
  from nhl.quantitative_roster_delta import compare
 except ModuleNotFoundError:
  from quantitative_roster_delta import compare
 result=compare(history,baseline,expected,as_of)
 result["returning_ids"]=result["incoming_ids"]
 result["unavailable_ids"]=result["outgoing_ids"]
 result["position_replacement_effect_validated"]=False
 result["defensive_effect"]=None
 result["roster_effect_on_ml_rt_3glp"]=None
 return result
