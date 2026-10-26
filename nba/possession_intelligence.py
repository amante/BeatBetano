"""NBA possession-driven pregame features and conservative lineup verification.

ESPN completed boxscores are postgame historical observations. Never classify
current starters from past starters, projections, or headlines.
"""
import argparse,json,statistics,re
from datetime import datetime,timezone
from pathlib import Path
import requests
URL="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
METRICS={"fieldGoalsAttempted":("fieldGoalsAttempted","fga"),
 "freeThrowsAttempted":("freeThrowsAttempted","fta"),
 "offensiveRebounds":("offensiveRebounds","orb"),
 "turnovers":("turnovers","to")}
def extract(payload,fixture):
 comps=payload.get("header",{}).get("competitions",[])
 if not comps or str(comps[0].get("id"))!=str(fixture["game_id"]):raise ValueError("Game mismatch")
 if comps[0].get("status",{}).get("type",{}).get("completed") is not True:raise ValueError("Not final")
 groups=payload.get("boxscore",{}).get("teams",[])
 result={}
 for row in groups:
  team=row.get("team",{}).get("abbreviation")
  if team not in (fixture["home_team"],fixture["away_team"]):raise ValueError("Team mismatch")
  stats={str(x.get("name")):x.get("displayValue",x.get("value")) for x in row.get("statistics",[]) if isinstance(x,dict)}
  def num(*names):
   for name in names:
    if name in stats:
     try:return float(stats[name])
     except (ValueError,TypeError):pass
   return None
  def attempts(*names):
   for name in names:
    val=stats.get(name)
    if isinstance(val,str):
     matched=re.fullmatch(r"\\s*([0-9]+)\\s*[-/]\\s*([0-9]+)\\s*",val)
     if matched:return float(matched.group(2))
   return None
  fga=num("fieldGoalsAttempted","fga")
  if fga is None:fga=attempts("fieldGoalsMade-fieldGoalsAttempted","fieldGoals","fieldGoalsMadeAttempted")
  fta=num("freeThrowsAttempted","fta")
  if fta is None:fta=attempts("freeThrowsMade-freeThrowsAttempted","freeThrows","freeThrowsMadeAttempted")
  orb=num("offensiveRebounds","offRebounds","offensiveReboundsTotal")
  turnovers=num("turnovers","totalTurnovers","to")
  pts=num("points","PTS")
  if pts is None:
   match=next((x for x in comps[0].get("competitors",[]) if x.get("team",{}).get("abbreviation")==team),None)
   if match:pts=float(match["score"])
  missing=[key for key,val in (("FGA",fga),("FTA",fta),("ORB",orb),("TOV",turnovers),("PTS",pts)) if val is None]
  if missing:raise ValueError("Missing boxscore fields "+team+": "+",".join(missing)+"; available="+",".join(sorted(stats)))
  poss=fga+0.44*fta-orb+turnovers
  if not 50<=poss<=160 or not 0<=pts<=250:continue
  result[team]={"possessions_estimated":poss,"points":pts}
 if set(result)!={fixture["home_team"],fixture["away_team"]}:raise ValueError("Incomplete team stats")
 return result

def capture(history,limit=80,session=None):
 request=session or requests.Session()
 rows=[];errors=[]
 for game in history[-limit:]:
  try:
   resp=request.get(URL,params={"event":str(game["game_id"])},timeout=20)
   resp.raise_for_status()
   stats=extract(resp.json(),game)
   for team,values in stats.items():
    opponent=game["away_team"] if team==game["home_team"] else game["home_team"]
    rows.append({"game_id":str(game["game_id"]),"tipoff_utc":game["tipoff_utc"],"team":team,
     "opponent":opponent,**values})
  except (requests.RequestException,ValueError,TypeError,KeyError) as exc:
   errors.append({"game_id":str(game["game_id"]),"error":type(exc).__name__,"detail":str(exc)[:500]})
 return {"games":rows,"source":URL,"errors":errors,"postgame_history_only":True}

def lineup_confirmed(entry,tip,team):
 if not isinstance(entry,dict):return []
 observed=entry.get("observed_at_utc")
 try:
  moment=datetime.fromisoformat(observed.replace("Z","+00:00"))
  cutoff=datetime.fromisoformat(tip.replace("Z","+00:00"))
 except (AttributeError,ValueError):return []
 if moment.tzinfo is None or moment>=cutoff:return []
 if entry.get("team")!=team or entry.get("is_confirmed") is not True or not entry.get("source_url"):return []
 players=entry.get("starters",[])
 if not isinstance(players,list) or len(players)!=5 or len(set(players))!=5 or any(not isinstance(p,str) or not p.strip() for p in players):return []
 return players

def build(snapshot,history,observations,lineups=None):
 if not observations.get("postgame_history_only"):raise ValueError("Expected postgame history data")
 games={str(g["game_id"]):g for g in history}
 by_team={}
 for row in observations["games"]:
  g=games.get(str(row["game_id"]))
  if not g or row.get("tipoff_utc")!=g.get("tipoff_utc"):continue
  if row["team"] not in (g["home_team"],g["away_team"]):continue
  by_team.setdefault(row["team"],[]).append(row)
 output={}
 for future in snapshot["predictions"]:
  tip=future["tipoff_utc"];teams=(future["home_team"],future["away_team"])
  stats={}
  for team in teams:
   previous=sorted((r for r in by_team.get(team,[]) if r["tipoff_utc"]<tip),key=lambda r:r["tipoff_utc"])[-10:]
   # Historical context only; must not treat sample as a validated forecast.
   n=len(previous)
   poss=statistics.mean(r["possessions_estimated"] for r in previous) if n>=3 else None
   offense=statistics.mean(100*r["points"]/r["possessions_estimated"] for r in previous) if n>=3 else None
   allowed=[]
   for r in previous:
    match=next((o for o in observations["games"] if str(o["game_id"])==str(r["game_id"]) and o["team"]==r["opponent"]),None)
    if match and match["possessions_estimated"]>0:
     allowed.append(100*match["points"]/match["possessions_estimated"])
   defense=statistics.mean(allowed) if len(allowed)>=3 else None
   confirmed=lineup_confirmed((lineups or {}).get(str(future["game_id"]),{}).get(team),tip,team)
   stats[team]={"confirmed_starters":confirmed,"starting_five_status":"confirmed" if len(confirmed)==5 else "unavailable",
    "sample_games":n,"offensive_rating":round(offense,2) if offense is not None else None,
    "defensive_rating":round(defense,2) if defense is not None else None,
    "historical_possessions":round(poss,2) if poss is not None else None,
    "historical_points_per_possession":round(offense/100,3) if offense is not None else None,
    "scoring_possession_rate_pct":None}
  a,b=stats[teams[0]],stats[teams[1]]
  estimated=round((a["historical_possessions"]+b["historical_possessions"])/2,1) if a["historical_possessions"] is not None and b["historical_possessions"] is not None else None
  projected={}
  for team in teams:
   own,opp=stats[team],stats[teams[1] if team==teams[0] else teams[0]]
   ppp=(own["offensive_rating"]+opp["defensive_rating"])/200 if own["offensive_rating"] is not None and opp["defensive_rating"] is not None else None
   projected[team]={"possessions_projected":estimated,"matchup_points_per_possession":round(ppp,3) if ppp is not None else None,
   "projected_points":round(estimated*ppp,1) if estimated is not None and ppp is not None else None}
  output[str(future["game_id"])]={"teams":stats,"projections":projected,
   "all_starters_confirmed":all(stats[t]["starting_five_status"]=="confirmed" for t in teams),
   "probability_adjustment_authorized":False}
 return {"games":output,"snapshot_sha256":snapshot["content_sha256"],"no_odds_input":True,
 "limitations":"ORtg/DRtg and possessions derived from sampled completed-game boxscores; projected PPP is a transparent uncalibrated opponent-average heuristic. Scoring-possession percentage requires play-by-play scoring possession counts. No validated probability adjustment."}

def markdown(report):
 out=["## NBA — Quintetos, eficiencia y posesiones","","**Historial observado y proyección exploratoria; no sustituyen titulares confirmados ni probabilidades validadas.**",""]
 for gid,g in report["games"].items():
  out.append("### "+gid)
  out.append("| Equipo | Quinteto confirmado | ORtg | DRtg | Posesiones esperadas | PPP esperado | Puntos esperados | % posesiones anotadas |")
  out.append("|---|---|---:|---:|---:|---:|---:|---:|")
  for team,stats in g["teams"].items():
   pred=g["projections"][team]
   fmt=lambda v:"—" if v is None else str(v)
   starters=", ".join(stats["confirmed_starters"]) if stats["confirmed_starters"] else "No verificado"
   out.append(f'| {team} | {starters} | {fmt(stats["offensive_rating"])} | {fmt(stats["defensive_rating"])} | {fmt(pred["possessions_projected"])} | {fmt(pred["matchup_points_per_possession"])} | {fmt(pred["projected_points"])} | — |')
 out+=["","Las tasas por posesión de anotación requieren secuencias play-by-play; no equivalen a puntos/posesión."]
 return "\n".join(out)+"\n"
def main():
 p=argparse.ArgumentParser()
 for name in ("snapshot","history","observations","output","summary"):p.add_argument("--"+name,required=True)
 p.add_argument("--lineups")
 a=p.parse_args()
 load=lambda path:json.loads(Path(path).read_text())
 report=build(load(a.snapshot),load(a.history),load(a.observations),load(a.lineups) if a.lineups else None)
 for filename,contents in ((a.output,json.dumps(report,indent=2)),(a.summary,markdown(report))):
  path=Path(filename);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(contents)
 print(json.dumps({"games":len(report["games"]),"confirmed_games":sum(g["all_starters_confirmed"] for g in report["games"].values())}))
if __name__=="__main__":main()
