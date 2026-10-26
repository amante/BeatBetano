"""Audit per-game NBA official Elo, challenger and hybrid probability comparisons."""
import argparse,json,math
from pathlib import Path

def audit(report):
 if report.get("sport")!="nba":raise ValueError("NBA report expected")
 rows=[]
 for game in report.get("games",[]):
  elo=game["official_elo_home"];challenge=game["challenger_home"]
  hybrid=game["statistical_baseline_home"]
  if any(type(p) not in (float,int) or not math.isfinite(p) or not 0<p<1
    for p in (elo,challenge,hybrid)):raise ValueError("Invalid model probabilities")
  route=game.get("hybrid_route","unknown")
  if route=="challenger" and abs(hybrid-challenge)>1e-9:
   raise ValueError("Hybrid challenger route does not match challenger")
  if route in ("insufficient_recent_sample","strong_favorite") and abs(hybrid-elo)>1e-9:
   raise ValueError("Hybrid Elo route does not match Elo")
  rows.append({"game_id":game["game_id"],"away":game["away_team"],"home":game["home_team"],
    "elo_p_home":elo,"challenger_p_home":challenge,"hybrid_p_home":hybrid,
    "delta_challenger_vs_elo_pp":round((challenge-elo)*100,2),
    "delta_hybrid_vs_elo_pp":round((hybrid-elo)*100,2),
    "hybrid_route":route,"integrated_p_home":game.get("integrated_home"),
    "sporting_impact_included":False,"validated":False})
 return {"games":rows,"game_count":len(rows),"no_odds_inputs":True,
  "calibration_passed":False,"note":"Comparative statistical estimates only. Recovered injury/news evidence has not yet been incorporated into these estimates."}

def markdown(data):
 lines=["## NBA | Base Elo vs Challenger vs Híbrido","","**Probabilidades estadísticas preliminares; no calibradas ni autorizadas para apostar.**","",
 "| Visitante @ Local | Elo local | Challenger local | Híbrido local | Δ Challenger–Elo | Δ Híbrido–Elo | Ruta |",
 "|---|---:|---:|---:|---:|---:|---|"]
 for g in data["games"]:
  pct=lambda p:f"{p*100:.1f}%"
  lines.append(f'| {g["away"]} @ {g["home"]} | {pct(g["elo_p_home"])} | {pct(g["challenger_p_home"])} | {pct(g["hybrid_p_home"])} | {g["delta_challenger_vs_elo_pp"]:+.2f} pp | {g["delta_hybrid_vs_elo_pp"]:+.2f} pp | {g["hybrid_route"]} |')
 lines+=["","Los tres valores reflejan el historial de resultados, forma y descanso previstos por los modelos actuales. Lesiones, titulares y matchups recuperados aún no ajustan estas probabilidades."]
 return "\n".join(lines)+"\n"

def main():
 p=argparse.ArgumentParser()
 for arg in ("input","output","summary"):p.add_argument("--"+arg,required=True)
 args=p.parse_args()
 report=audit(json.loads(Path(args.input).read_text()))
 for path,value in ((args.output,json.dumps(report,indent=2)),(args.summary,markdown(report))):
  target=Path(path);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(value)
 print(json.dumps({"games":report["game_count"],"calibration_passed":False}))
if __name__=="__main__":main()
