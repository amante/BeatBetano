"""Collect ESPN per-game preview evidence without upgrading projections to confirmed lineups.

The official NBA injury report is a separate continuously updated PDF series.
We archive live game summaries and conservative extracts; never infer starter
confirmation from a postgame box score or an undocumented API key.
"""
import argparse,json
from pathlib import Path
from datetime import datetime,timezone
import requests

SUMMARY="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"

def extract_game(payload,game,observed):
    if not isinstance(payload,dict):raise ValueError("Bad ESPN summary payload")
    eid=str(game["game_id"])
    header=payload.get("header",{})
    competitions=header.get("competitions",[]) if isinstance(header,dict) else []
    if competitions:
        comp=competitions[0]
        reported=str(comp.get("id",eid))
        if reported!=eid:raise ValueError("Summary event does not match requested fixture")
    injuries=payload.get("injuries",[])
    # Preserve source-specific claims as observations, never verification.
    if not isinstance(injuries,list):injuries=[]
    observations=[]
    for group in injuries:
        if not isinstance(group,dict):continue
        for player in group.get("injuries",[]):
            if not isinstance(player,dict):continue
            athlete=player.get("athlete",{})
            name=athlete.get("displayName") if isinstance(athlete,dict) else None
            if not name:continue
            observations.append({"player":name,"status":player.get("status"),
                  "source":"ESPN summary","officially_verified":False})
    return {"game_id":eid,"observed_at_utc":observed,"source_url":SUMMARY+"?event="+eid,
            "injury_observations":observations,
            "confirmed_starting_lineups":None,
            "confirmed_rotation_minutes":None,
            "positional_matchups":None,
            "lineup_status":"unverified",
            "is_pregame_evidence":True,
            "note":"ESPN summary observations are not confirmation of starting fives."}

def collect(snapshot,session=None):
    clock=datetime.now(timezone.utc)
    request=session or requests.Session()
    games={}
    for g in snapshot["predictions"]:
        tip=datetime.fromisoformat(g["tipoff_utc"].replace("Z","+00:00"))
        if tip<=clock:continue
        try:
            response=request.get(SUMMARY,params={"event":str(g["game_id"])},timeout=30)
            response.raise_for_status()
            games[str(g["game_id"])]=extract_game(response.json(),g,clock.isoformat())
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            games[str(g["game_id"])]={
                "game_id":str(g["game_id"]),"observed_at_utc":clock.isoformat(),
                "source_url":SUMMARY+"?event="+str(g["game_id"]),
                "injury_observations":[],"confirmed_starting_lineups":None,
                "lineup_status":"unverified","is_pregame_evidence":False,
                "retrieval_status":"unavailable",
                "retrieval_error_type":type(exc).__name__,
                "note":"ESPN evidence unavailable for this game; no missing players assumed healthy."}
    return {"snapshot_sha256":snapshot["content_sha256"],
            "source":"ESPN game preview; supplementary, not official NBA starter confirmation",
            "games":games}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    result=collect(json.loads(Path(a.snapshot).read_text()))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2))
    print(json.dumps({"game_previews_collected":len(result["games"]),
                      "confirmed_lineups":0},indent=2))

if __name__=="__main__":main()
