"""NFL pregame matchup evidence from ESPN game summaries.

Preserves raw source observations. No starter/coverage scheme, weather forecast,
injury impact, player prop probability or calibrated winner claim inferred.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import requests

SUMMARY="https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"

def moment(value):
    date=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if date.tzinfo is None:raise ValueError("Timestamp requires timezone")
    return date.astimezone(timezone.utc)

def observe_game(game,payload,observed_at):
    stamp=moment(observed_at)
    kickoff=moment(game["start_utc"])
    if stamp>=kickoff:raise ValueError("Not pregame evidence")
    header=payload.get("header",{})
    events=header.get("competitions",[])
    if not events or str(events[0].get("id"))!=str(game["event_id"]):
        raise ValueError("Game ID mismatch")
    competitors=events[0].get("competitors",[])
    actual={v.get("team",{}).get("abbreviation") for v in competitors}
    expected={game["home_team"],game["away_team"]}
    if actual!=expected:raise ValueError("Team mismatch")
    groups=[]
    raw=payload.get("injuries",[])
    if isinstance(raw,list):
        for block in raw:
            team=block.get("team",{}) if isinstance(block,dict) else {}
            name=team.get("abbreviation")
            if name not in expected:continue
            players=[]
            for item in block.get("injuries",[]):
                athlete=item.get("athlete",{}) if isinstance(item,dict) else {}
                if not isinstance(athlete,dict):continue
                label=athlete.get("displayName")
                if label:
                    players.append({"name":label,"status":item.get("status"),
                                    "position":athlete.get("position",{}).get("abbreviation")
                                    if isinstance(athlete.get("position"),dict) else None,
                                    "confirmed_inactive":False})
            groups.append({"team":name,"observations":players})
    return {"event_id":str(game["event_id"]),"source":SUMMARY,
            "observed_at_utc":stamp.isoformat(),
            "before_tipoff_verified":True,"injury_observations":groups,
            "injuries_officially_confirmed":False,"starting_qbs_verified":False,
            "ol_and_secondary_starters_verified":False,
            "coverage_scheme_verified":False,"weather_forecast_verified":False,
            "snap_projections_verified":False,"prop_probabilities_verified":False,
            "candidate_probability_adjustment":None,
            "note":"ESPN summary injury listings are supplementary, not final official inactives."}

def collect(slate,session=None,observed_at=None):
    if slate.get("sport")!="nfl":raise ValueError("NFL slate required")
    when=observed_at or datetime.now(timezone.utc).isoformat()
    client=session or requests.Session()
    records=[]
    for g in slate.get("events",[]):
        try:
            if moment(when)>=moment(g["start_utc"]):
                records.append({"event_id":g["event_id"],"availability":"started_before_collection"})
                continue
            response=client.get(SUMMARY,params={"event":g["event_id"]},timeout=30)
            response.raise_for_status()
            records.append(observe_game(g,response.json(),when))
        except (requests.RequestException,ValueError,TypeError,KeyError,AttributeError):
            records.append({"event_id":g["event_id"],"availability":"source_unavailable",
                            "candidate_probability_adjustment":None})
    return {"schema_version":1,"sport":"nfl","observed_at_utc":when,
            "source":SUMMARY,"games":records,
            "impact_model_training_authorized":False,
            "note":"No market odds. Observations alone do not establish starters or injury effects."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--slate",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    report=collect(json.loads(Path(a.slate).read_text()))
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2))
    print(json.dumps({"games":len(report["games"]),"verified_live_impacts":0}))
if __name__=="__main__":main()
