"""Chronological, exploratory audit of NBA hybrid sample gates.

Never changes production predictions or claims independent holdout success.
Each variant observes only state before the game being scored.
"""
import argparse,json
from pathlib import Path
from model import evaluate
from challenger import predict_challenger
from guardrails import guardrail
from feature_impact_audit import metrics

def route(elo,challenger,nh,na,minimum):
 if min(nh,na)<minimum:return elo,"sample_gate"
 if max(elo,1-elo)>=.80:return elo,"strong_favorite"
 return challenger,"challenger"

def audit(history):
 games=sorted(history,key=lambda g:(g["tipoff_utc"],str(g["game_id"])))
 if not games:raise ValueError("Empty history")
 if len({str(g["game_id"]) for g in games})!=len(games):raise ValueError("Duplicate IDs")
 elo=list(evaluate(games,season_min=min(int(g["season"]) for g in games),season_max=max(int(g["season"]) for g in games)))
 challenger=predict_challenger(games)
 versions={"current_gate_3":3,"gate_0":0,"gate_1":1,"gate_2":2,"gate_5":5}
 accum={}
 for game,e,c in zip(games,elo,challenger):
  if game["home_points"] is None or game["away_points"] is None:continue
  season=str(game["season"])
  y=int(game["home_points"]>game["away_points"])
  bucket=accum.setdefault(season,{key:{"scores":[],"routes":{}} for key in ["elo","challenger",*versions]})
  for key,p,why in [("elo",e.p_home,"elo"),("challenger",c["p_home"],"challenger")]+[
   (name,*route(e.p_home,c["p_home"],c["n_home"],c["n_away"],threshold)) for name,threshold in versions.items()]:
   bucket[key]["scores"].append((p,y))
   bucket[key]["routes"][why]=bucket[key]["routes"].get(why,0)+1
 return {"seasons":{season:{key:{**metrics(data["scores"]),"route_counts":data["routes"]} for key,data in block.items()} for season,block in accum.items()},
  "production_gate_unchanged":True,"independent_holdout_passed":False,"selection_authorized":False,
  "note":"Exploratory thresholds 0/1/2/3/5 were examined on historical data; no winner may be selected from these same seasons as independently validated."}

def markdown(result):
 out=["## NBA — Hybrid minimum-sample gate sensitivity","",
 "**Exploratory diagnostic. No production-rule change or independent holdout proof.**","",
 "| Season | Variant | n | Brier | Log loss | Sample gate count |",
 "|---|---|---:|---:|---:|---:|"]
 for season,variants in sorted(result["seasons"].items()):
  for name,m in variants.items():
   out.append(f'| {season} | {name} | {m["n"]} | {m["brier"]} | {m["log_loss"]} | {m["route_counts"].get("sample_gate",0)} |')
 out+=["","Thresholds are exploratory alternatives to the existing 3-games-per-team requirement. All evaluations use pre-outcome state and no market odds."]
 return "\n".join(out)+"\n"
def main():
 p=argparse.ArgumentParser()
 for k in ("history","output","summary"):p.add_argument("--"+k,required=True)
 a=p.parse_args();r=audit(json.loads(Path(a.history).read_text()))
 for path,body in ((a.output,json.dumps(r,indent=2)),(a.summary,markdown(r))):
  dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(body)
 print(json.dumps({"seasons":list(r["seasons"]),"production_rule_changed":False}))
if __name__=="__main__":main()
