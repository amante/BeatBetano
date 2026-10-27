"""Live NHL roster and club skater data, captured before puck drop.

This is *observed data*, not confirmed game lines, active lineup or calibrated CRS.
Official public endpoints only; reject started games and never backfill old runs.
"""
import argparse,json
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
import requests

API="https://api-web.nhle.com/v1"
def utc(x):
 d=datetime.fromisoformat(str(x).replace("Z","+00:00"))
 if d.tzinfo is None:raise ValueError("Timezone required")
 return d.astimezone(timezone.utc)

def names(p):
 def word(k):
  v=p.get(k,{});return v.get("default","") if isinstance(v,dict) else str(v or "")
 return (word("firstName")+" "+word("lastName")).strip()

def measure(roster,stats,team,freeze):
 if not isinstance(roster,dict) or not isinstance(stats,dict):
  return {"team":team,"status":"source_unavailable","skaters":[]}
 ids={p["id"]:p for group in ("forwards","defensemen") for p in roster.get(group,[])
      if isinstance(p,dict) and type(p.get("id")) is int}
 players=[]
 for x in stats.get("skaters",[]):
  pid=x.get("playerId")
  if pid not in ids:continue
  gp=x.get("gamesPlayed");pts=x.get("points")
  if type(gp) is not int or gp<=0 or type(pts) is not int or pts<0:continue
  p=ids[pid]
  players.append({"player_id":pid,"name":names(p),"position":p.get("positionCode"),
                  "games_played":gp,"points":pts,"goals":x.get("goals"),
                  "assists":x.get("assists"),"points_per_game":round(pts/gp,3)})
 players.sort(key=lambda x:(-x["points_per_game"],-x["games_played"],x["player_id"]))
 forwards=sum(1 for p in ids.values() if p.get("positionCode")!="D")
 defense=sum(1 for p in ids.values() if p.get("positionCode")=="D")
 return {"team":team,"status":"measured_roster_intersection" if players else "no_current_season_skaters",
         "roster_forwards":forwards,"roster_defense":defense,
         "skaters":[]+players,"ranked_by":"points_per_game_not_line_assignment",
         "top_six_points_per_game":[p["points_per_game"] for p in players[:6]],
         "confirmed_lineup":False,"unit_ratings":None,"crs":None,
         "roster_source":API+"/roster/"+team+"/current",
         "stats_source":API+"/club-stats/"+team+"/"+str(int(freeze[:4])-(int(freeze[5:7])<7))*0 if False else None}

def capture(slate,fetch):
 if slate.get("sport")!="nhl":raise ValueError("NHL slate required")
 freeze=utc(slate["as_of_utc"])
 teams={}
 for g in slate["events"]:
  if utc(g["start_utc"])<=freeze:raise ValueError("No retrospective/started fixtures")
  for side in ("home","away"):teams[g[side+"_team"]]=True
 season_start=freeze.year-(freeze.month<7)
 season=f"{season_start}{season_start+1}"
 def pull(team):
  roster_url=f"{API}/roster/{team}/current"
  stats_url=f"{API}/club-stats/{team}/{season}/2"
  try:
   roster=fetch(roster_url)
   try:
    stats=fetch(stats_url)
   except (requests.RequestException,ValueError,KeyError,TypeError):
    stats_url=f"{API}/club-stats/{team}/now"
    stats=fetch(stats_url)
   out=measure(roster,stats,team,slate["as_of_utc"])
   out["roster_source"]=roster_url;out["stats_source"]=stats_url
   return team,out
  except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
   return team,{"team":team,"status":"source_unavailable","error_type":type(exc).__name__,"error_detail":str(exc)[:250],"skaters":[],
                "roster_source":roster_url,"stats_source":stats_url,
                "crs":None,"unit_ratings":None,"confirmed_lineup":False}
 with ThreadPoolExecutor(max_workers=6) as pool:
  futures=[pool.submit(pull,team) for team in sorted(teams)]
  for f in as_completed(futures):
   team,record=f.result();teams[team]=record
 return {"sport":"nhl","as_of_utc":slate["as_of_utc"],"season":season,
         "teams":teams,"official_sources_only":True,
         "point_in_time_note":"Endpoint fetched at generation; requires archived immutable snapshot for retrospective reproducibility",
         "not_confirmed_lines":True,"calibrated":False}

def summary(report):
 rows=["## NHL real player data — official NHL API",
       "Current roster intersection with current-season skater totals. **PPG ranking is not top-six deployment or confirmed starters.**","",
       "| Team | Roster F | Roster D | Skaters with GP | Top observed PPG players | Status |",
       "|---|---:|---:|---:|---|---|"]
 for team,r in sorted(report["teams"].items()):
  leaders=", ".join(f'{p["name"]} {p["points_per_game"]:.2f}' for p in r.get("skaters",[])[:3]) or "—"
  rows.append(f'| {team} | {r.get("roster_forwards","—")} | {r.get("roster_defense","—")} | {len(r.get("skaters",[]))} | {leaders} | {r["status"]} |')
 rows.append("\n**Not yet calculated:** effective CRS, actual units, starting goalies, sustainable PP/PK and calibrated probabilities.")
 return "\n".join(rows)+"\n"

def main():
 p=argparse.ArgumentParser()
 for name in ("slate","output","summary"):p.add_argument("--"+name,required=True)
 a=p.parse_args();slate=json.loads(Path(a.slate).read_text())
 def fetch(url):
  r=requests.get(url,timeout=25);r.raise_for_status();return r.json()
 out=capture(slate,fetch)
 if out["teams"] and not any(record.get("skaters") for record in out["teams"].values()):
  raise RuntimeError("Zero NHL skaters; refusing false success. "+str({k:(v["status"],v.get("error_detail")) for k,v in out["teams"].items()}))
 for filename,value in ((a.output,json.dumps(out,indent=2)),(a.summary,summary(out))):
  target=Path(filename);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(value)
 print(json.dumps({"teams":len(out["teams"]),"with_skaters":sum(bool(r.get("skaters")) for r in out["teams"].values())}))
if __name__=="__main__":main()
