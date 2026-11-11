"""NFL hoy: live scoreboard classification and odds-free historical Elo baseline.

Source: ESPN public scoreboard + completed nflverse games ledger.
No roster, injury, weather or prop probabilities are invented.
"""
import sys
import argparse,json,math,hashlib,os
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from multisport.daily_forecasts import publish
import requests

URL="https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

def utc(value):
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None:return d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def fixtures(payload,as_of):
    if not isinstance(payload.get("events"),list):raise ValueError("No ESPN events array")
    now=utc(as_of);rows=[];seen=set();counts={"scheduled":0,"started":0,"completed":0}
    for e in payload["events"]:
        c=e.get("competitions",[])
        if len(c)!=1:continue
        teams={x.get("homeAway"):x for x in c[0].get("competitors",[])}
        if set(teams)!={"home","away"}:continue
        status=c[0].get("status",e.get("status",{})).get("type",{})
        if e.get("season",{}).get("type") not in (2,"2"):continue
        eid=str(e.get("id",""))
        tip=utc(e.get("date"))
        home=teams["home"].get("team",{}).get("abbreviation")
        away=teams["away"].get("team",{}).get("abbreviation")
        if not eid or eid in seen or not home or not away or home==away:raise ValueError("Bad or duplicate NFL fixture")
        seen.add(eid)
        if status.get("completed") is True:counts["completed"]+=1
        elif tip<=now or status.get("state")!="pre":counts["started"]+=1
        else:
            counts["scheduled"]+=1
            rows.append({"event_id":eid,"start_utc":tip.isoformat(),"participants":[home,away],
                         "home_team":home,"away_team":away})
    return sorted(rows,key=lambda x:(x["start_utc"],x["event_id"])),counts

def _prepared_history(games,cutoff):
    prepared=[]
    for r in games:
        try:
            tip=utc(str(r["gameday"])+"T00:00:00Z")
            year=int(r["season"])
            hs=float(r["home_score"]);aw=float(r["away_score"])
            h=str(r["home_team"]);a=str(r["away_team"])
        except (KeyError,ValueError,TypeError):continue
        if tip>=cutoff or not math.isfinite(hs) or not math.isfinite(aw) or hs==aw:continue
        if r.get("game_type") not in (None,"REG","WC","DIV","CON","SB"):continue
        prepared.append((tip,year,h,a,hs,aw))
    return sorted(prepared)


def elo(games,cutoff):
    ratings={};season=None
    prepared=_prepared_history(games,cutoff)
    for (day,yr),batch in __import__("itertools").groupby(prepared,key=lambda r:(r[0],r[1])):
        rows=list(batch)
        if season is not None and yr!=season:
            ratings={t:1500+.75*(v-1500) for t,v in ratings.items()}
        season=yr
        updates=[]
        for _,_,h,a,hs,aw in rows:
            p=1/(1+10**(-(ratings.get(h,1500)-ratings.get(a,1500)+55)/400))
            updates.append((h,a,20*((hs>aw)-p)))
        for h,a,delta in updates:
            ratings[h]=ratings.get(h,1500)+delta
            ratings[a]=ratings.get(a,1500)-delta
    return ratings,len(prepared)

def report(payload,ledger,as_of):
    now=utc(as_of);games,status=fixtures(payload,as_of)
    ratings,n=elo(ledger,now)
    training_rows=_prepared_history(ledger,now)
    training_payload=[{"gameday":row[0].date().isoformat(),"season":row[1],"home_team":row[2],
                       "away_team":row[3],"home_score":row[4],"away_score":row[5]}
                      for row in training_rows]
    training_cutoff=training_rows[-1][0].isoformat() if training_rows else None
    for g in games:
        home,away=g["participants"]
        p=1/(1+10**(-(ratings.get(home,1500)-ratings.get(away,1500)+55)/400))
        g.update({"official_baseline":None,"historical_elo_candidate":round(p,6),
            "challenger":None,"final_probability":None,"away_probability":None,
            "all_inputs_verified":False,"independent_validation_passed":False,
            "starting_lineups_verified":False,"injury_report_verified":False,
            "weather_verified":False,"props":None,
            "missing_evidence":["confirmed_inactives","starters","weather","matchups","independent_calibration"]})
    model_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return {"schema_version":1,"command":"NFL hoy","sport":"nfl","as_of_utc":now.isoformat(),
      "model_provenance":{"model_code_sha256":model_code_sha256},
      "odds_used_in_sport_model":False,"events":games,"event_status_counts":status,
      "historical_games_used":n,"complete_vs_league":False,
      "model_provenance":{"data_role":"historical_elo_training_history",
        "training_data_sha256":hashlib.sha256(json.dumps(training_payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest(),
        "training_cutoff_utc":training_cutoff,"model_code_revision":os.environ.get("GITHUB_SHA") or None,
        "model_family":"nfl-historical-elo"},
      "note":"Historical Elo exploratory candidate only; no official calibrated model or injury-adjusted/prop picks."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True)
    p.add_argument("--date",required=True,help="ESPN US league calendar YYYY-MM-DD")
    p.add_argument("--output",required=True)
    p.add_argument('--forecast-archive',help='Persistent per-event forecast revision directory')
    x=p.parse_args()
    now=datetime.now(timezone.utc).isoformat()
    day=datetime.fromisoformat(x.date).strftime("%Y%m%d")
    response=requests.get(URL,params={"dates":day,"limit":100},timeout=40)
    response.raise_for_status()
    import csv
    with Path(x.history).open(newline="") as f:ledger=list(csv.DictReader(f))
    data=report(response.json(),ledger,now)
    output=Path(x.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(data,indent=2))
    publication=publish('nfl',data,x.forecast_archive or output.parent/'forecast_archive',revision='nfl-historical-elo',live_only=True)
    output.with_name(output.stem+'.forecasts.json').write_text(json.dumps(publication,indent=2))
    print(json.dumps({"pregame":len(data["events"]),"statuses":data["event_status_counts"],
                      "historical_games_used":data["historical_games_used"]}))
if __name__=="__main__":main()
