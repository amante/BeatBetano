"""PULSO PLAYER v3: multi-skater NHL roster discovery and team-rest research replay."""
import argparse,csv,json,math
from collections import defaultdict
from datetime import date,datetime,timezone
from pathlib import Path
from nhl.pulso_player_ingest_v2 import API,SEASONS,fetch_json,to_minutes
from nhl.pulso_player_v1 import validate,forecast

ROSTER="https://api-web.nhle.com/v1/roster/{team}/{season}"
SCHEDULE="https://api-web.nhle.com/v1/club-schedule-season/{team}/{season}"
TEAMS=("ANA","BOS","BUF","CAR","CBJ","CGY","CHI","COL","DAL","DET","EDM","FLA","LAK","MIN","MTL","NJD","NSH","NYI","NYR","OTT","PHI","PIT","SEA","SJS","STL","TBL","TOR","UTA","VAN","VGK","WPG","WSH")
def roster_ids(team,season,fetch):
 data=fetch(ROSTER.format(team=team,season=season))
 if not isinstance(data,dict):raise ValueError("Invalid roster response")
 result={}
 for bucket in ("forwards","defensemen"):
  if not isinstance(data.get(bucket),list):raise ValueError("Missing roster bucket "+bucket)
  for row in data[bucket]:
   player=str(row["id"])
   result[player]={"position":str(row["positionCode"]),"team":team}
 return result
def schedule_rest(team,season,fetch):
 url=SCHEDULE.format(team=team,season=season)
 data=fetch(url)
 if not isinstance(data,dict) or not isinstance(data.get("games"),list):raise ValueError("Schedule missing games")
 games=sorted((g for g in data["games"] if g.get("gameType")==2 and g.get("gameDate") and g.get("id")),key=lambda g:(g["gameDate"],str(g["id"])))
 out={};previous=None
 for g in games:
  d=date.fromisoformat(g["gameDate"])
  rest=None if previous is None else (d-previous).days-1
  if rest is not None and rest<0:raise ValueError("Duplicate team game date")
  out[str(g["id"])]=(rest,d.isoformat())
  previous=d
 return out,url
def build(teams,seasons,fetch=fetch_json):
 identities={};sources=[];schedules={}
 for season in seasons:
  for team in teams:
   u=ROSTER.format(team=team,season=season)
   identities.update(roster_ids(team,season,fetch))
   sources.append({"url":u,"kind":"roster","season":season,"team":team})
   schedule,url=schedule_rest(team,season,fetch)
   schedules[(team,season)]=schedule
   sources.append({"url":url,"kind":"schedule","season":season,"team":team})
 records=[];positions={}
 for player,identity in sorted(identities.items()):
  positions[player]=identity["position"]
  for season in seasons:
   url=API.format(player=player,season=season)
   data=fetch(url)
   if not isinstance(data,dict) or not isinstance(data.get("gameLog"),list):
    raise ValueError("Bad player log "+url)
   sources.append({"url":url,"kind":"player_log","player":player,"season":season,"rows":len(data["gameLog"])})
   for g in data["gameLog"]:
    game=str(g["gameId"]);team=g["teamAbbrev"]
    # Don't mix skater logs with team schedule from an unsupported club.
    if team not in teams:continue
    mapping=schedules.get((team,season),{})
    info=mapping.get(game)
    if info is None or info[0] is None:continue
    rest,scheduled_date=info
    if g["gameDate"]!=scheduled_date:raise ValueError("Game date mismatch")
    records.append({"game_id":game,"date":scheduled_date,"player_id":player,
      "team":team,"opponent":g["opponentAbbrev"],"home":g["homeRoadFlag"]=="H",
      "rest_days":rest,"toi_minutes":to_minutes(g["toi"]),
      "shots_on_goal":int(g["shots"]),"goals":int(g["goals"])})
 return validate(records),positions,sources
def evaluate(rows,positions,start="2025-10-01"):
 # v1 forecast needs team and player prior records. Replay each skater on its own
 # historical dates and aggregate position + team-rest cohorts without hindsight.
 by_player=defaultdict(list)
 for r in rows:by_player[r["player_id"]].append(r)
 groups=defaultdict(list);individual=[]
 for pid,games in by_player.items():
  for index,row in enumerate(games):
   if row["date"]<start or index<3:continue
   target={k:row[k] for k in ("player_id","team","opponent","home","rest_days")}
   f=forecast(games[:index],target,row["date"])
   if f["projection"] is None:continue
   group=("defense" if positions.get(pid) in ("D","LD","RD") else "forward")
   segment="b2b" if row["rest_days"]==0 else ("one_day" if row["rest_days"]==1 else "two_plus")
   record={"player_id":pid,"date":row["date"],"game_id":row["game_id"],"position_group":group,"rest_group":segment,"actual":{k:row[k] for k in f["projection"]},"contextual":f["projection"],"baseline":f["unconditional_average"]}
   individual.append(record)
   for category in ("all",group,segment):
    groups[category].append(record)
 def metrics(subset):
  results={}
  for stat in ("toi_minutes","shots_on_goal","goals"):
   n=len(subset)
   baseline=sum(abs(x["baseline"][stat]-x["actual"][stat]) for x in subset)/n if n else None
   contextual=sum(abs(x["contextual"][stat]-x["actual"][stat]) for x in subset)/n if n else None
   results[stat]={"n":n,"baseline_mae":round(baseline,6) if n else None,
     "contextual_mae":round(contextual,6) if n else None,
     "improvement_pct":round(100*(baseline-contextual)/baseline,3) if baseline else None}
  return results
 return {"status":"research_only_not_validated","segments":{k:metrics(v) for k,v in sorted(groups.items())},
   "players_evaluated":len(set(r["player_id"] for r in individual)),"observations":len(individual),
   "rows":individual,"limitations":["Retrospective roster season lists may include transfers or players not active on a target date; only historical game appearances are evaluated.","Team rest uses season regular schedule; timezone effects/neutral site not yet modeled.","Goal projections use point MAE, not calibrated goal scoring probabilities."]}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--teams",default="EDM",help="Comma-separated teams or ALL")
 p.add_argument("--seasons",default=",".join(SEASONS))
 p.add_argument("--start",default="2025-10-01")
 p.add_argument("--out",required=True)
 a=p.parse_args()
 teams=TEAMS if a.teams=="ALL" else tuple(x.strip().upper() for x in a.teams.split(","))
 if not teams or any(t not in TEAMS for t in teams):raise ValueError("Unknown NHL team")
 seasons=tuple(a.seasons.split(","))
 if not seasons or any(s not in SEASONS for s in seasons):raise ValueError("Unsupported season")
 rows,positions,sources=build(teams,seasons)
 report=evaluate(rows,positions,a.start)
 dest=Path(a.out);dest.mkdir(parents=True,exist_ok=True)
 (dest/"metrics.json").write_text(json.dumps({k:v for k,v in report.items() if k!="rows"},indent=2))
 (dest/"predictions.json").write_text(json.dumps(report["rows"]))
 (dest/"provenance.json").write_text(json.dumps({"retrieved_at":datetime.now(timezone.utc).isoformat(),"teams":teams,"seasons":seasons,"sources":sources,"raw_rows":len(rows),"distinct_players":len(positions)},indent=2))
 print(json.dumps({"players":report["players_evaluated"],"observations":report["observations"],"segments":report["segments"]},indent=2))
if __name__=="__main__":main()
