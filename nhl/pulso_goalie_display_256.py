"""Human-readable goalie review from roster-verified fixture identity."""
import argparse,json
from pathlib import Path

def render(identity, daily):
 indexed={str(g["game_id"]):g for g in daily["games"]}
 lines=["GAME | TEAM | GOALIE | STATUS | SV% SEASON | SV% RECENT"]
 for game in identity["games"]:
  metrics=indexed.get(str(game["game_id"]))
  if not metrics:raise ValueError("Missing goalie fixture")
  if (metrics["home"],metrics["away"])!=(game["home"],game["away"]):raise ValueError("Fixture teams mismatch")
  for team in (game["home"],game["away"]):
   source=game["teams"][team]
   row=metrics["teams"][team]
   if source["source_goalie_player_id"]!=row["nhl_player_id"]:raise ValueError("Player ID mismatch")
   name=source.get("source_goalie_name") or "Aún sin identificar"
   state="Confirmado" if source["independent_goalie_confirmation"] else "Probable" if source["source_goalie_player_id"] else "Sin confirmar"
   sv=str(row.get("season_sv_pct")) if row.get("status")=="descriptive_evidence_only" else "No disponible"
   recent=str(row.get("recent_5_sv_pct")) if row.get("status")=="descriptive_evidence_only" else "No disponible"
   lines.append(f'{game["away"]}@{game["home"]} | {team} | {name} | {state} | {sv} | {recent}')
 return "\n".join(lines)+"\n"
def main():
 p=argparse.ArgumentParser()
 for x in ("identity","daily","out"):p.add_argument("--"+x,required=True)
 a=p.parse_args()
 text=render(json.loads(Path(a.identity).read_text()),json.loads(Path(a.daily).read_text()))
 Path(a.out).write_text(text)
 print(text)
if __name__=="__main__":main()
