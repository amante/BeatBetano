"""Official NHL current roster snapshot, with explicit epistemic limits.

A current roster is an *eligibility candidate pool*, not a verified game lineup,
starting goalie, injuries, scratches, lines, or pregame availability. Every
snapshot gets a precise fetch timestamp and original SHA256 for audit.
"""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

HOST="https://api-web.nhle.com"
GROUPS={"forwards":"forward","defensemen":"defense","goalies":"goalie"}
def parse_roster(payload,team,observed_at):
    if not re.fullmatch(r"[A-Z]{3}",team):raise ValueError("Invalid NHL club code")
    if not isinstance(payload,dict):raise ValueError("NHL roster payload must be JSON object")
    players=[];ids=set()
    for group,role in GROUPS.items():
        entries=payload.get(group)
        if not isinstance(entries,list):raise ValueError("Missing official roster group "+group)
        for player in entries:
            if not isinstance(player,dict) or not isinstance(player.get("id"),int):
                raise ValueError("Invalid official roster player")
            pid=player["id"]
            if pid in ids:raise ValueError("Duplicate official roster ID")
            ids.add(pid)
            players.append({"player_id":pid,"position_group":role,
                "position_code":player.get("positionCode"),"roster_membership":"listed",
                "lineup_status":"unknown","starter_confirmed":False,
                "expected_share":None})
    if not players:raise ValueError("No players in roster response")
    return {"team":team,"as_of":observed_at,"source_url":f"{HOST}/v1/roster/{team}/current",
        "source_kind":"official_current_team_roster_not_match_lineup",
        "players":players,"players_count":len(players),
        "lineup_confirmed":False,"injury_status_known":False,
        "goalie_starter_confirmed":False,"odds_used":False}

def fetch(team,timeout=25):
    if not re.fullmatch(r"[A-Z]{3}",team):raise ValueError("Invalid club")
    url=f"{HOST}/v1/roster/{team}/current"
    with urlopen(Request(url,headers={"User-Agent":"BeatBetano-research/1.0","Accept":"application/json"}),timeout=timeout) as r:
        raw=r.read(2_000_000)
        if r.read(1):raise ValueError("Oversized response")
    now=datetime.now(timezone.utc).isoformat()
    record=parse_roster(json.loads(raw),team,now)
    record["source_sha256"]=hashlib.sha256(raw).hexdigest()
    return record

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--teams",nargs="+",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    teams=sorted(set(a.teams))
    if len(teams)>32:raise ValueError("Too many clubs")
    records=[fetch(t) for t in teams]
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(records,indent=2))
    print(json.dumps({"teams":len(records),"listed_players":sum(r["players_count"] for r in records),
     "confirmed_starting_goalies":0,"confirmed_game_lineups":0,
     "notice":"Official current rosters are NOT game lineup confirmations."},indent=2))
if __name__=="__main__":main()
