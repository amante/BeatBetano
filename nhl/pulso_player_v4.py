"""PULSO PLAYER NHL v4: multi-team, strictly chronological probabilistic replay.

Poisson predictive count distributions are exploratory, not asserted calibrated.
No odds; every estimate uses only prior dated player games.
"""
import argparse,json,math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from nhl.pulso_player_v3 import TEAMS,build
from nhl.pulso_player_v1 import forecast

def poisson_probs(rate,cap=12):
 if rate<0 or not math.isfinite(rate):raise ValueError("Invalid rate")
 p0=math.exp(-rate)
 probs=[p0]
 for k in range(1,cap):probs.append(probs[-1]*rate/k)
 probs.append(max(0.,1-sum(probs)))
 return probs

def bin_probability(rate):
 return -math.expm1(-rate)

def binary_scores(predictions,outcomes):
 n=len(predictions)
 if not n:return {"n":0,"brier":None,"log_loss":None,"observed_rate":None,"expected_rate":None}
 eps=1e-12
 return {"n":n,"brier":round(sum((p-y)**2 for p,y in zip(predictions,outcomes))/n,6),
  "log_loss":round(-sum(y*math.log(max(p,eps))+(1-y)*math.log(max(1-p,eps)) for p,y in zip(predictions,outcomes))/n,6),
  "observed_rate":round(sum(outcomes)/n,6),"expected_rate":round(sum(predictions)/n,6)}

def summarize(records):
 out={}
 for name,subset in (("all",records),("forward",[r for r in records if r["position_group"]=="forward"]),
                     ("defense",[r for r in records if r["position_group"]=="defense"])):
  metrics={}
  for stat in ("toi_minutes","shots_on_goal","goals"):
   truth=[r["actual"][stat] for r in subset]
   pred={method:[r["predictions"][method][stat] for r in subset] for method in ("historical","recent5","recent10","contextual")}
   metrics[stat]={"n":len(subset),"mae":{k:round(sum(abs(a-b) for a,b in zip(v,truth))/len(truth),6) if truth else None for k,v in pred.items()}}
  for stat in ("shots_on_goal","goals"):
   actual=[int(r["actual"][stat]>=1) for r in subset]
   metrics[stat]["at_least_one"]={method:binary_scores([r["probabilities"][method][stat] for r in subset],actual)
      for method in ("historical","recent5","recent10","contextual")}
  out[name]=metrics
 return out

def replay(rows,positions,start="2025-10-01"):
 by_player=defaultdict(list)
 for r in rows:by_player[r["player_id"]].append(r)
 results=[]
 for pid,games in by_player.items():
  for index,r in enumerate(games):
   if r["date"]<start:continue
   # Compare on precisely the same forecast sample: at least ten earlier
   # appearances for rolling-10 and context forecast. No current-game inputs.
   prior=[x for x in games[:index] if x["team"]==r["team"] and x["date"]<r["date"]]
   if len(prior)<10:continue
   target={k:r[k] for k in ("player_id","team","opponent","home","rest_days")}
   contextual=forecast(prior,target,r["date"])
   if contextual["projection"] is None:continue
   keys=("toi_minutes","shots_on_goal","goals")
   estimates={"contextual":contextual["projection"],"historical":contextual["unconditional_average"]}
   for n in (5,10):
    window=prior[-n:]
    estimates[f"recent{n}"]={k:sum(x[k] for x in window)/n for k in keys}
   probs={method:{stat:bin_probability(values[stat]) for stat in ("shots_on_goal","goals")}
     for method,values in estimates.items()}
   results.append({"player_id":pid,"team":r["team"],"date":r["date"],"game_id":r["game_id"],
    "position_group":"defense" if positions.get(pid) in ("D","LD","RD") else "forward",
    "rest_days":r["rest_days"],"actual":{k:r[k] for k in keys},
    "predictions":estimates,"probabilities":probs})
 return results

def bootstrap_interval(records,stat="toi_minutes",samples=300):
 """Deterministic player-cluster bootstrap; positive value means MAE improvement."""
 import random
 clusters=defaultdict(list)
 for r in records:clusters[r["player_id"]].append(r)
 ids=sorted(clusters)
 if len(ids)<2:return None
 rng=random.Random(20261029);deltas=[]
 for _ in range(samples):
  chosen=[rng.choice(ids) for _ in ids]
  sample=[r for pid in chosen for r in clusters[pid]]
  base=sum(abs(r["predictions"]["historical"][stat]-r["actual"][stat]) for r in sample)/len(sample)
  ctx=sum(abs(r["predictions"]["contextual"][stat]-r["actual"][stat]) for r in sample)/len(sample)
  deltas.append(base-ctx)
 deltas.sort()
 return {"cluster":"player","resamples":samples,"mae_improvement_ci95":[round(deltas[int(.025*samples)],6),round(deltas[min(samples-1,int(.975*samples))],6)]}

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--teams",default="EDM,COL,DAL,FLA,NYR,TOR",help="Comma-separated NHL teams; ALL is high API load")
 p.add_argument("--seasons",default="20232024,20242025,20252026,20262027")
 p.add_argument("--start",default="2025-10-01")
 p.add_argument("--out",required=True)
 a=p.parse_args()
 teams=TEAMS if a.teams=="ALL" else tuple(t.strip().upper() for t in a.teams.split(","))
 if not teams or len(set(teams))!=len(teams) or any(t not in TEAMS for t in teams):raise ValueError("Invalid teams")
 seasons=tuple(a.seasons.split(","))
 if not seasons or any(s not in ("20232024","20242025","20252026","20262027") for s in seasons):raise ValueError("Invalid seasons")
 rows,positions,sources=build(teams,seasons)
 predictions=replay(rows,positions,a.start)
 report={"status":"research_not_production","teams_requested":teams,"rows_ingested":len(rows),
   "players_scored":len(set(r["player_id"] for r in predictions)),"observations":len(predictions),
   "metrics":summarize(predictions),"uncertainty":{k:bootstrap_interval(predictions,k) for k in ("toi_minutes","shots_on_goal","goals")},
   "assumptions":["Poisson count model is a provisional distribution; no proof of calibration.","Pregame roster and availability are not independently reconstructed; only observed participants are replayed.","All competitors evaluated on same >=10-prior-game sample; trade/team history uses current-team prior rows.","Bootstrapped CI groups by player within the selected teams; cannot establish league-wide generalization."]}
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 (out/"metrics.json").write_text(json.dumps(report,indent=2))
 (out/"dated_predictions.json").write_text(json.dumps(predictions))
 (out/"provenance.json").write_text(json.dumps({"source":"NHL API","retrieved_at":datetime.now(timezone.utc).isoformat(),"sources":sources,"teams":teams,"seasons":seasons},indent=2))
 print(json.dumps({k:report[k] for k in ("teams_requested","players_scored","observations","metrics","uncertainty")},indent=2))
if __name__=="__main__":main()
