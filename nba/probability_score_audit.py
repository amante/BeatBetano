"""Flag direction disagreements between frozen win probability and uncalibrated score projection.

No adjustment to existing probabilities. Separate evidence from model output.
"""
import argparse,json,math
from pathlib import Path

def audit(snapshot,possessions):
 if snapshot.get("content_sha256")!=possessions.get("snapshot_sha256"):
  raise ValueError("Snapshot mismatch")
 forecasts={str(p["game_id"]):p for p in snapshot["predictions"]}
 inputs=possessions.get("games",{})
 if set(inputs)!=set(forecasts):raise ValueError("Slate mismatch")
 result=[]
 for gid,p in forecasts.items():
  matchup=inputs[gid];home=p["home_team"];away=p["away_team"]
  projections=matchup["projections"]
  scores=[projections[t].get("projected_points") for t in (home,away)]
  valid=all(type(v) in (int,float) and math.isfinite(v) for v in scores)
  margin=round(scores[0]-scores[1],2) if valid else None
  probabilities={name:p[f"{name}_p_home"] for name in ("elo","challenger","hybrid")}
  for name,prob in probabilities.items():
   if type(prob) not in (int,float) or not 0<prob<1:raise ValueError("Invalid probability")
  disagreement={name:bool(margin is not None and margin!=0 and (prob-.5)*margin<0)
                for name,prob in probabilities.items()}
  result.append({"game_id":gid,"home_team":home,"away_team":away,
   "elo_p_home":probabilities["elo"],"challenger_p_home":probabilities["challenger"],
   "hybrid_p_home":probabilities["hybrid"],"projected_home_points":scores[0],
   "projected_away_points":scores[1],"projected_home_margin":margin,
   "hybrid_route":p.get("hybrid_route"),
   "direction_disagreement":disagreement,
   "requires_manual_review":disagreement["hybrid"],
   "probability_adjustment_authorized":False})
 return {"snapshot_sha256":snapshot["content_sha256"],"games":result,
  "hybrid_disagreements":sum(g["requires_manual_review"] for g in result),
  "no_odds_input":True,"sporting_adjustment_applied":False,
  "note":"Heuristic projected scores and statistical win probabilities are different models. Direction disagreement requires review; no spread-to-probability mapping is calibrated."}

def markdown(data):
 rows=["## NBA — Auditoría de dirección: ML vs puntos proyectados","",
 "**Alerta ≠ probabilidad nueva. No se alteran los snapshots.**","",
 "| Partido | Elo local | Challenger local | Híbrido local | Puntos local | Puntos visitante | Margen local | Conflicto híbrido |",
 "|---|---:|---:|---:|---:|---:|---:|---|"]
 for g in data["games"]:
  pct=lambda p:f"{100*p:.1f}%"
  num=lambda p:"—" if p is None else str(p)
  rows.append(f'| {g["away_team"]} @ {g["home_team"]} | {pct(g["elo_p_home"])} | {pct(g["challenger_p_home"])} | {pct(g["hybrid_p_home"])} | {num(g["projected_home_points"])} | {num(g["projected_away_points"])} | {num(g["projected_home_margin"])} | {"REVISAR" if g["requires_manual_review"] else "No"} |')
 rows.extend(["",f'**Conflictos detectados: {data["hybrid_disagreements"]}.**',
 "Los puntos esperados provienen de una heurística ofensiva/defensiva no calibrada. Las probabilidades todavía no incorporan esas métricas."])
 return "\n".join(rows)+"\n"

def main():
 p=argparse.ArgumentParser()
 for arg in ("snapshot","possessions","output","summary"):p.add_argument("--"+arg,required=True)
 a=p.parse_args()
 result=audit(json.loads(Path(a.snapshot).read_text()),json.loads(Path(a.possessions).read_text()))
 for name,value in ((a.output,json.dumps(result,indent=2)),(a.summary,markdown(result))):
  f=Path(name);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(value)
 print(json.dumps({"games":len(result["games"]),"hybrid_disagreements":result["hybrid_disagreements"]}))
if __name__=="__main__":main()
