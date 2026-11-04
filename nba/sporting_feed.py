"""NBA sporting evidence collector: independent observations, not certified lineup inputs.

Public ESPN injury endpoint is supplementary, not the NBA's official report.
Stores source/time and team-specific extracts but NEVER marks lineups/injuries
as verified without official reconciliation. No bookmaker odds are read.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
import requests
from team_identity import same_team

INJURIES_URL="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
SUMMARY_URL="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
OFFICIAL_INJURY_REPORT="https://official.nba.com/nba-injury-report-2026-27-season/"

def extract(payload, snapshot, collected_at):
    if not isinstance(payload,dict):raise ValueError("ESPN injury feed not an object")
    if not isinstance(payload.get("injuries"),list):raise ValueError("ESPN missing injuries array")
    result={}
    rejected=[]
    for game in snapshot["predictions"]:
        rows=[]
        for group in payload["injuries"]:
            if not isinstance(group,dict):continue
            group_team=group.get("team",{})
            group_abbr=group_team.get("abbreviation") if isinstance(group_team,dict) else None
            for injury in group.get("injuries",[]):
                if not isinstance(injury,dict):continue
                athlete=injury.get("athlete",{})
                if not isinstance(athlete,dict):continue
                player_team=athlete.get("team",{})
                player_team=player_team if isinstance(player_team,dict) else {}
                player_abbr=player_team.get("abbreviation")
                # Current feed puts team identity on the athlete, while legacy
                # responses put it on the group. Conflicting identities are not joined.
                if group_abbr and player_abbr and not same_team(group_abbr,player_abbr):
                    rejected.append({"game_id":str(game["game_id"]),"player":athlete.get("displayName"),"reason":"conflicting_team_abbreviations"})
                    continue
                if group.get("id") and player_team.get("id") and str(group["id"])!=str(player_team["id"]):
                    rejected.append({"game_id":str(game["game_id"]),"player":athlete.get("displayName"),"reason":"conflicting_team_ids"})
                    continue
                abbr=player_abbr or group_abbr
                team=next((t for t in (game["home_team"],game["away_team"]) if same_team(t,abbr)),None)
                if team is None:continue
                name=athlete.get("displayName")
                if not name:continue
                rows.append({"team":team,"source_team":abbr,"player":name,
                             "player_id":str(athlete["id"]) if athlete.get("id") else None,
                             "status":injury.get("status"),"reported_at_utc":injury.get("date"),
                             "detail":injury.get("details",{}).get("detail") if isinstance(injury.get("details"),dict) else None})
        result[str(game["game_id"])]={
          "supplementary_injury_observations":{"source":INJURIES_URL,
              "observed_at_utc":collected_at,"items":rows,
              "source_verified_official":False},
          "official_report_reference":OFFICIAL_INJURY_REPORT,
          "starting_lineups_confirmed":False,
          "rotations_verified":False,
          "matchups_verified":False,
          "complete_pregame":False}
    return {"source":"ESPN supplementary injuries, not official NBA verification",
            "collected_at_utc":collected_at,"games":result,"rejected_claims":rejected}

def collect(snapshot,session=None):
    requester=session or requests.Session()
    response=requester.get(INJURIES_URL,timeout=35)
    response.raise_for_status()
    return extract(response.json(),snapshot,datetime.now(timezone.utc).isoformat())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--snapshot",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    snap=json.loads(Path(args.snapshot).read_text())
    result=collect(snap)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x") as f:json.dump(result,f,indent=2)
    print(json.dumps({"games":len(result["games"]),
      "observations":sum(len(x["supplementary_injury_observations"]["items"]) for x in result["games"].values()),
      "confirmed_lineups":0,"official_injury_verifications":0},indent=2))
if __name__=="__main__":main()
