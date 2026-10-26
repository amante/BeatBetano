"""Chronological NBA Elo/Challenger/hybrid sports-feature ablation.
Scores postgame outcomes against predictions computed before each outcome.
Historical comparison is exploratory, NOT independent holdout approval.
"""
import argparse,json,math
from pathlib import Path
from model import evaluate
from challenger import predict_challenger
from guardrails import guardrail

def metrics(rows):
 if not rows:return {"n":0,"brier":None,"log_loss":None}
 n=len(rows)
 return {"n":n,"brier":round(sum((p-y)**2 for p,y in rows)/n,6),
 "log_loss":round(-sum(y*math.log(max(1e-12,min(1-1e-12,p)))+
 (1-y)*math.log(max(1e-12,min(1-1e-12,1-p))) for p,y in rows)/n,6)}
def audit(history):
 if not history:raise ValueError("Missing historical games")
 games=sorted(history,key=lambda x:(x["tipoff_utc"],str(x["game_id"])))
 if len({str(g["game_id"]) for g in games})!=len(games):raise ValueError("Duplicate games")
 first=min(int(g["season"]) for g in games)
 last=max(int(g["season"]) for g in games)
 elo=list(evaluate(games,season_min=first,season_max=last))
 full=predict_challenger(games)
 only_margin=predict_challenger(games,use_rest=False)
 only_rest=predict_challenger(games,use_margin=False)
 buckets={}
 for g,e,c,m,r in zip(games,elo,full,only_margin,only_rest):
  if g["home_points"] is None or g["away_points"] is None:continue
  season=str(g["season"])
  target=int(g["home_points"]>g["away_points"])
  hybrid,route=guardrail(e.p_home,c["p_home"],c["n_home"],c["n_away"])
  row=buckets.setdefault(season,{"elo":[],"challenger":[],"hybrid":[],"margin_only":[],"rest_only":[],"route_counts":{}})
  for name,p in (("elo",e.p_home),("challenger",c["p_home"]),("hybrid",hybrid),
    ("margin_only",m["p_home"]),("rest_only",r["p_home"])):
   row[name].append((p,target))
  row["route_counts"][route]=row["route_counts"].get(route,0)+1
 seasons={}
 for season,items in buckets.items():
  seasons[season]={"models":{k:metrics(items[k]) for k in
   ("elo","challenger","hybrid","margin_only","rest_only")},"route_counts":items["route_counts"]}
 return {"seasons":seasons,"chronological":True,"market_odds_used":False,
 "independent_holdout_passed":False,"production_approved":False,
 "limitations":"Coefficients/guardrails were previously inspected on historical seasons. This is an ablation diagnostic, not a new untouched holdout or calibrated injury/lineup model."}
def markdown(result):
 out=["## NBA: chronological sporting-factor ablation","","**Exploratory diagnostic, not independent calibration.**","",
 "| Season | Model | n | Brier | Log loss |","|---|---|---:|---:|---:|"]
 for season,data in sorted(result["seasons"].items()):
  for name,values in data["models"].items():
   out.append(f'| {season} | {name} | {values["n"]} | {values["brier"]} | {values["log_loss"]} |')
 out+=["","Margin-only and rest-only remove the other Challenger coefficient while retaining Elo. No bookmaker odds, live injury status or confirmed starters used."]
 return "\n".join(out)+"\n"
def main():
 p=argparse.ArgumentParser()
 for k in ("history","output","summary"):p.add_argument("--"+k,required=True)
 a=p.parse_args();r=audit(json.loads(Path(a.history).read_text()))
 for path,value in ((a.output,json.dumps(r,indent=2)),(a.summary,markdown(r))):
  t=Path(path);t.parent.mkdir(parents=True,exist_ok=True);t.write_text(value)
 print(json.dumps({"seasons":list(r["seasons"]),"independent_holdout_passed":False}))
if __name__=="__main__":main()
