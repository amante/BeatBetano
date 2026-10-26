"""Experimental NBA probability challenger informed by possession-based scoring margins.

Never replaces the frozen Base/Challenger/Hybrid or claims independent validation.
A margin-to-win conversion is a hypothesis with explicit uncertainty, not a fit.
"""
import argparse,json,math
from pathlib import Path

def phi(x):
 return 0.5*(1+math.erf(x/math.sqrt(2)))
def candidate(hybrid,home_points,away_points,sigma=13.5,weight=0.25):
 if type(hybrid) not in (int,float) or not 0<hybrid<1:raise ValueError("Invalid hybrid probability")
 if not 5<=sigma<=50 or not 0<=weight<=1:raise ValueError("Invalid hypothesis parameters")
 if home_points is None or away_points is None:return None
 if not all(type(x) in (int,float) and math.isfinite(x) for x in (home_points,away_points)):
  raise ValueError("Nonfinite projection")
 margin=home_points-away_points
 score_probability=phi(margin/sigma)
 return {"score_margin_home":round(margin,3),"score_model_p_home":round(score_probability,6),
  "experimental_p_home":round((1-weight)*hybrid+weight*score_probability,6),
  "uncertainty_sigma_points":sigma,"blend_weight":weight,
  "production_approved":False}
def audit(snapshot,possessions):
 if snapshot.get("content_sha256")!=possessions.get("snapshot_sha256"):
  raise ValueError("Snapshot digest mismatch")
 games=possessions.get("games",{})
 if set(games)!={str(x["game_id"]) for x in snapshot["predictions"]}:
  raise ValueError("Incomplete/mismatched slate")
 output=[]
 for g in snapshot["predictions"]:
  match=games[str(g["game_id"])]
  projection=match["projections"]
  home=projection[g["home_team"]]["projected_points"]
  away=projection[g["away_team"]]["projected_points"]
  result=candidate(g["hybrid_p_home"],home,away)
  output.append({"game_id":g["game_id"],"home_team":g["home_team"],"away_team":g["away_team"],
   "elo_p_home":g["elo_p_home"],"challenger_p_home":g["challenger_p_home"],
   "hybrid_p_home":g["hybrid_p_home"],"possession_challenger":result,
   "point_in_time_snapshot":snapshot["content_sha256"],
   "status":"exploratory_not_calibrated" if result else "insufficient_sporting_features"})
 return {"games":output,"snapshot_sha256":snapshot["content_sha256"],
  "no_odds_input":True,"production_probabilities_unchanged":True,
  "independent_validation_passed":False,
  "warning":"0.25 blend weight and 13.5-point sigma are declared test hypotheses, not validated coefficients. Do not bet using this probability."}
def markdown(report):
 lines=["## NBA — Challenger experimental basado en posesiones","",
 "**NO calibrado: no modifica Base, Challenger o Híbrido de producción.**","",
 "| Partido | Base | Challenger | Híbrido | Margen proyectado local | P(local) experimental |",
 "|---|---:|---:|---:|---:|---:|"]
 fmt=lambda x:"—" if x is None else f"{x*100:.1f}%"
 for g in report["games"]:
  c=g["possession_challenger"]
  lines.append(f'| {g["away_team"]} @ {g["home_team"]} | {fmt(g["elo_p_home"])} | {fmt(g["challenger_p_home"])} | {fmt(g["hybrid_p_home"])} | {c["score_margin_home"] if c else "—"} | {fmt(c["experimental_p_home"]) if c else "—"} |')
 lines+=["","La dispersión 13,5 puntos y la ponderación 25% son hipótesis de investigación; se deben validar antes de utilizar como pronósticos finales."]
 return "\n".join(lines)+"\n"
def main():
 p=argparse.ArgumentParser()
 for name in ("snapshot","possessions","output","summary"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 report=audit(json.loads(Path(a.snapshot).read_text()),json.loads(Path(a.possessions).read_text()))
 for dest,data in ((a.output,json.dumps(report,indent=2)),(a.summary,markdown(report))):
  f=Path(dest);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(data)
 print(json.dumps({"games":len(report["games"]),"features_available":sum(g["possession_challenger"] is not None for g in report["games"]),"validated":False}))
if __name__=="__main__":main()
