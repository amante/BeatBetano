"""NBA two-way offense-versus-opponent-defense matchup audit.

Only verified prior boxscore team aggregates enter ratings. Scheme/player matchup
evidence is explicitly unavailable unless observed; never guess coverage assignments.
"""
import argparse,json,math
from pathlib import Path

def evaluate(snapshot,report):
 if snapshot.get("content_sha256")!=report.get("snapshot_sha256"):
  raise ValueError("Snapshot mismatch")
 outcomes={}
 for game in snapshot["predictions"]:
  gid=str(game["game_id"]);row=report.get("games",{}).get(gid)
  if not row:raise ValueError("Missing matchup "+gid)
  home=game["home_team"];away=game["away_team"]
  stats=row["teams"];projections=row["projections"]
  edges={}
  for team,opp in ((home,away),(away,home)):
   attack=stats[team].get("offensive_rating")
   defense=stats[opp].get("defensive_rating")
   own_defense=stats[team].get("defensive_rating")
   if any(type(x) not in (int,float) or not math.isfinite(x) for x in (attack,defense,own_defense)):
    edges[team]={"status":"insufficient_verified_team_sample"}
    continue
   n=min(stats[team].get("sample_games",0),stats[opp].get("sample_games",0))
   # This is a transparent pairwise descriptive comparison; NOT trained impact.
   ppp=(attack+defense)/200
   edges[team]={"status":"team_level_only","attack_ortg":attack,"opponent_drtg":defense,
    "own_drtg":own_defense,"sample_games_min":n,
    "opponent_defensive_concession_vs_own_attack":round(defense-attack,2),
    "pairwise_ppp":round(ppp,4),"projected_possessions":projections[team].get("possessions_projected"),
    "projected_points":projections[team].get("projected_points"),
    "player_vs_defender_matchups_verified":False,
    "scheme_matchups_verified":False,"lineup_matchups_verified":False}
  hp=projections[home].get("projected_points")
  ap=projections[away].get("projected_points")
  margin=round(hp-ap,2) if all(type(x) in (int,float) and math.isfinite(x) for x in (hp,ap)) else None
  outcomes[gid]={"home_team":home,"away_team":away,"matchups":edges,
   "projected_home_margin":margin,"hybrid_p_home":game["hybrid_p_home"],
   "direction_conflict":margin is not None and margin!=0 and (game["hybrid_p_home"]-.5)*margin<0,
   "matchup_adjustment_authorized":False}
 return {"snapshot_sha256":snapshot["content_sha256"],"games":outcomes,
 "no_odds_input":True,"player_matchups_verified":False,"production_adjustment_authorized":False,
 "note":"Pairs offensive rating against opponent defensive rating in both directions. Scheme/positional individual assignments are not inferred from team-level boxscores."}

def markdown(data):
 lines=["## NBA — Ataque contra defensa rival: pareos bidireccionales","",
 "**Contexto descriptivo, no impacto probabilístico calibrado. Pareos individuales aún sin evidencia verificable.**","",
 "| Partido | ORtg local vs DRtg rival | ORtg visitante vs DRtg rival | PPP local | PPP visitante | Margen local | Conflicto Híbrido |",
 "|---|---|---|---:|---:|---:|---|"]
 for row in data["games"].values():
  h,a=row["home_team"],row["away_team"];x,y=row["matchups"][h],row["matchups"][a]
  fmt=lambda v:"—" if v is None else str(v)
  duo=lambda z: f'{z["attack_ortg"]} / {z["opponent_drtg"]}' if z.get("status")=="team_level_only" else "—"
  lines.append(f'| {a} @ {h} | {duo(x)} | {duo(y)} | {fmt(x.get("pairwise_ppp"))} | {fmt(y.get("pairwise_ppp"))} | {fmt(row["projected_home_margin"])} | {"REVISAR" if row["direction_conflict"] else "No"} |')
 lines+=["","Pendiente para pareos jugador-defensor: quintetos confirmados, asignaciones defensivas, tiro por zona, frecuencia de pick-and-roll, cambios y protección del aro.","No se alteran probabilidades Base, Challenger ni Híbrido."]
 return "\n".join(lines)+"\n"

def main():
 p=argparse.ArgumentParser()
 for arg in ("snapshot","possessions","output","summary"):p.add_argument("--"+arg,required=True)
 a=p.parse_args();r=evaluate(json.loads(Path(a.snapshot).read_text()),json.loads(Path(a.possessions).read_text()))
 for dest,content in ((a.output,json.dumps(r,indent=2)),(a.summary,markdown(r))):
  f=Path(dest);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(content)
 print(json.dumps({"games":len(r["games"]),"adjustment_authorized":False}))
if __name__=="__main__":main()
