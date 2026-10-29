"""PULSO NHL v5: strictly pre-date hybrid forecasts and chronological calibration.

Candidate hybrid weights are chosen on preceding dated games only, using
one season as a test split. No user-facing pregame player availability implied.
"""
import argparse,json,math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from nhl.pulso_player_v3 import TEAMS,build
from nhl.pulso_player_v4 import replay as v4_replay, binary_scores,bin_probability

WEIGHTS=(0.,.25,.5,.75,1.)
def blend(a,b,weight):
 return (1-weight)*a+weight*b
def season_of(day):
 year=int(day[:4]);month=int(day[5:7])
 return f"{year if month>=7 else year-1}{year+1 if month>=7 else year}"
def bins(records,field,groups=10):
 output=[]
 for i in range(groups):
  subset=[r for r in records if min(groups-1,int(r["probabilities"]["hybrid"][field]*groups))==i]
  output.append({"bin":i,"n":len(subset),
   "predicted":round(sum(r["probabilities"]["hybrid"][field] for r in subset)/len(subset),6) if subset else None,
   "observed":round(sum(r["actual"][field]>=1 for r in subset)/len(subset),6) if subset else None})
 return output
def select_weights(training,stat):
 # Selection is restricted to preceding seasons; no tuning to eval targets.
 if not training:return .5
 losses={}
 for w in WEIGHTS:
  losses[w]=sum(abs(blend(r["predictions"]["recent10"][stat],r["predictions"]["contextual"][stat],w)-r["actual"][stat]) for r in training)/len(training)
 return min(WEIGHTS,key=lambda w:(losses[w],abs(w-.5)))
def evaluate(rows,positions,start="2025-10-01"):
 # Create only prior-date base predictions (v4). Forward-test whole 2025-26
 # then 2026-27, tuning only on previous seasons' prior-dated predictions.
 base=v4_replay(rows,positions,start="2024-10-01")
 by_season=defaultdict(list)
 for r in base:by_season[season_of(r["date"])].append(r)
 targets=[s for s in sorted(by_season) if s>=season_of(start)]
 results=[];weight_schedule={}
 for season in targets:
  training=[r for s,g in by_season.items() if s<season for r in g]
  weights={k:select_weights(training,k) for k in ("toi_minutes","shots_on_goal","goals")}
  weight_schedule[season]={"weights":weights,"prior_season_examples":len(training)}
  for r in by_season[season]:
   estimate={k:max(0.,blend(r["predictions"]["recent10"][k],r["predictions"]["contextual"][k],weights[k])) for k in weights}
   # Shots-volume * past personal goal-per-shot conversion (Bayesian prior):
   # prior goal/shots must be reconstructed from earlier game outcomes, NOT
   # from the scored sample or target game.
   history=[g for g in rows if g["player_id"]==r["player_id"] and g["team"]==r["team"] and g["date"]<r["date"]]
   total_shots=sum(g["shots_on_goal"] for g in history)
   total_goals=sum(g["goals"] for g in history)
   conversion=(total_goals+1)/(total_shots+12)
   estimate["goals"]=max(0.,estimate["shots_on_goal"]*conversion)
   prob={k:bin_probability(estimate[k]) for k in ("shots_on_goal","goals")}
   results.append({**r,"season":season,"predictions":{**r["predictions"],"hybrid":estimate},
                   "probabilities":{**r["probabilities"],"hybrid":prob}})
 return results,weight_schedule
def summarize(records):
 metrics={}
 for scope,subset in [("all",records)]+[(s,[r for r in records if r["season"]==s]) for s in sorted(set(r["season"] for r in records))]+[(t,[r for r in records if r["team"]==t]) for t in sorted(set(r["team"] for r in records))]+[(p,[r for r in records if r["position_group"]==p]) for p in ("forward","defense")]:
  d={"n":len(subset)}
  for stat in ("toi_minutes","shots_on_goal","goals"):
   d[stat]={"mae":{method:round(sum(abs(r["predictions"][method][stat]-r["actual"][stat]) for r in subset)/len(subset),6) if subset else None for method in ("historical","recent5","recent10","contextual","hybrid")}}
   if stat!="toi_minutes":
    d[stat]["binary"]={method:binary_scores([r["probabilities"][method][stat] for r in subset],[int(r["actual"][stat]>=1) for r in subset]) for method in ("historical","recent5","recent10","contextual","hybrid")}
  metrics[scope]=d
 return metrics
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--teams",default="EDM,COL,DAL,FLA,NYR,TOR")
 p.add_argument("--start",default="2025-10-01")
 p.add_argument("--out",required=True)
 a=p.parse_args()
 teams=TEAMS if a.teams=="ALL" else tuple(t.strip().upper() for t in a.teams.split(","))
 if not teams or len(set(teams))!=len(teams) or any(t not in TEAMS for t in teams):raise ValueError("Invalid teams")
 rows,positions,sources=build(teams,("20232024","20242025","20252026","20262027"))
 predictions,weights=evaluate(rows,positions,a.start)
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 report={"status":"research_only","n":len(predictions),"players":len(set(r["player_id"] for r in predictions)),
  "weight_schedule":weights,"scores":summarize(predictions),
  "calibration":{stat:bins(predictions,stat) for stat in ("shots_on_goal","goals")},
  "limitations":["Season-boundary walk-forward; first evaluation season has precommitted default 50% weight if no prior-season scored games.","Retrospectively observed lineup participants, not pregame availability.","Poisson probabilities and conversion prior are research assumptions; test calibration by season/team.","Credited goals without SOG may occur, so conversion is only a smoothing heuristic, not an identity."]}
 (out/"metrics.json").write_text(json.dumps(report,indent=2))
 (out/"predictions.json").write_text(json.dumps(predictions))
 (out/"provenance.json").write_text(json.dumps({"retrieved_at_utc":datetime.now(timezone.utc).isoformat(),"sources":sources,"teams":teams},indent=2))
 print(json.dumps({"n":report["n"],"players":report["players"],"weights":weights,"scores":report["scores"]["all"]},indent=2))
if __name__=="__main__":main()
