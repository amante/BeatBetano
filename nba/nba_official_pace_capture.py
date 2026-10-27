"""NBA.com official aggregate pace observations, strictly dated before target games.

Research-only capture; no fallback to fabricated values or forecast override.
NBA Stats may throttle/block Actions traffic: surface failure as unavailable.
"""
import argparse,json
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import requests

URL="https://stats.nba.com/stats/leaguedashteamstats"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; research; +https://www.nba.com/)",
 "Referer":"https://www.nba.com/","Origin":"https://www.nba.com",
 "x-nba-stats-origin":"stats","x-nba-stats-token":"true"}
def parse(payload):
 sets=payload.get("resultSets") or ([payload["resultSet"]] if "resultSet" in payload else [])
 if not isinstance(sets,list) or not sets:raise ValueError("No NBA result sets")
 rows=[]
 for data in sets:
  header=data.get("headers",[]);values=data.get("rowSet",[])
  if not {"TEAM_ID","TEAM_NAME","GP","PACE","POSS","OFF_RATING","DEF_RATING","OREB_PCT","TM_TOV_PCT"}.issubset(header):continue
  for cells in values:
   if len(cells)!=len(header):raise ValueError("Malformed advanced NBA row")
   row=dict(zip(header,cells))
   if not isinstance(row["PACE"],(int,float)) or not isinstance(row["POSS"],(int,float)) or not isinstance(row["GP"],int):continue
   rows.append({k:row[k] for k in ("TEAM_ID","TEAM_NAME","GP","PACE","POSS","OFF_RATING","DEF_RATING","OREB_PCT","TM_TOV_PCT")})
 if not rows:raise ValueError("No compatible NBA advanced rows")
 return rows

def collect(game_date,session=None,observed_at=None):
 day=date.fromisoformat(game_date)
 observed=observed_at or datetime.now(timezone.utc).isoformat()
 now=datetime.fromisoformat(observed.replace("Z","+00:00"))
 if now.tzinfo is None:raise ValueError("UTC capture timestamp required")
 # Only use prior calendar dates even if request occurs midday.
 cutoff=min(day-timedelta(days=1),now.date()-timedelta(days=1))
 season_year=day.year if day.month>=10 else day.year-1
 season=f"{season_year}-{str((season_year+1)%100).zfill(2)}"
 params={"Season":season,"SeasonType":"Regular Season","MeasureType":"Advanced",
 "PerMode":"Totals","DateFrom":"","DateTo":cutoff.strftime("%m/%d/%Y"),
 "LastNGames":0,"LeagueID":"00","Month":0,"OpponentTeamID":0,"TeamID":0,
 "PlusMinus":"N","PaceAdjust":"N","Rank":"N"}
 result={"target_date":game_date,"cutoff_date":cutoff.isoformat(),
  "captured_at_utc":observed,"season":season,"source_url":URL,
  "status":"unavailable","teams":[],"no_odds_input":True,
  "production_probability_adjustment_authorized":False}
 try:
  response=(session or requests.Session()).get(URL,params=params,headers=HEADERS,timeout=18)
  response.raise_for_status()
  result["teams"]=parse(response.json())
  result["status"]="observed_unvalidated"
 except (requests.RequestException,ValueError,KeyError,TypeError) as exc:
  result["error_type"]=type(exc).__name__
 return result

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--date",required=True);p.add_argument("--output",required=True)
 args=p.parse_args();out=collect(args.date)
 f=Path(args.output);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(out,indent=2))
 print(json.dumps({"status":out["status"],"teams":len(out["teams"]),"cutoff":out["cutoff_date"]}))
if __name__=="__main__":main()
