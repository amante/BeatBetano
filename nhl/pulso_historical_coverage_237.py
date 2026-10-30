"""Coverage audit for prior-date team research dataset; not model validation."""
import argparse,json,math
from collections import Counter,defaultdict
from pathlib import Path

CORE=("prior_goalie_save_pct","prior_skater_goals_per_observed_game")
def audit(rows,min_games=5):
 if not isinstance(rows,list):raise ValueError("Expected list")
 seen=set();coverage=Counter();year=defaultdict(lambda:{"games":0,"eligible":0})
 team_year=defaultdict(lambda:{"games":0,"thin":0,"missing":Counter()})
 eligible=0
 for row in rows:
  gid=str(row.get("game_id",""))
  if not gid or gid in seen:raise ValueError("Missing or duplicate game")
  seen.add(gid)
  d=row["date"];home=row["home"];away=row["away"]
  if home==away:raise ValueError("Same team on both sides")
  if not isinstance(row.get("target"),dict):raise ValueError("Missing targets")
  ok=True
  for side,t in (("home",home),("away",away)):
   f=row["features"][side]
   if set(f)&{"ml_winner","rt_result","home_final_goals","away_final_goals"}:raise ValueError("Target leakage")
   g=team_year[(d[:4],t)];g["games"]+=1
   n=f.get("past_games")
   if isinstance(n,bool) or not isinstance(n,(int,float)) or not math.isfinite(n) or n<0:raise ValueError("Invalid games")
   if n<min_games:g["thin"]+=1;ok=False
   for key in CORE:
    v=f.get(key)
    if v is None:g["missing"][key]+=1;ok=False;continue
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:raise ValueError("Invalid feature")
    if key=="prior_goalie_save_pct" and v>1:raise ValueError("Invalid SV%")
    coverage[side+"_"+key]+=1
  year[d[:4]]["games"]+=1
  if ok:eligible+=1;year[d[:4]]["eligible"]+=1
 return {"status":"historical_sporting_coverage_research_only","games":len(rows),
  "eligible_games":eligible,"eligible_fraction":round(eligible/len(rows),6) if rows else 0,
  "minimum_prior_games":min_games,"core_counts":dict(coverage),"by_year":dict(sorted(year.items())),
  "by_team_year":[{"year":y,"team":t,"games":v["games"],"thin":v["thin"],
     "missing":dict(v["missing"])} for (y,t),v in sorted(team_year.items())],
  "odds_used":False,"model_promoted":False,
  "limits":"Team aggregates only; historical starter, lineup and individual availability not verified."}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--dataset",required=True);p.add_argument("--out",required=True)
 a=p.parse_args();x=audit(json.loads(Path(a.dataset).read_text()))
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(x,indent=2))
 print(json.dumps({k:x[k] for k in ("games","eligible_games","eligible_fraction","by_year")},indent=2))
if __name__=="__main__":main()
