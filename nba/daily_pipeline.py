"""End-to-end NBA pregame execution with independently verified historical ledger.

Fetches live fixtures and generates an immutable three-model snapshot. Historical
game data must be supplied and inspected separately; never fabricate team ratings.
"""
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from current_feed import fetch_day
from prospective import generate

def run(history,scoreboard,created_at):
    fixtures=scoreboard["future_fixtures"]
    if not fixtures:
        raise ValueError("No not-yet-started NBA regular-season games in scoreboard")
    if "as_of_utc" not in scoreboard:
        raise ValueError("Source snapshot timestamp missing")
    feed_at=datetime.fromisoformat(scoreboard["as_of_utc"].replace("Z","+00:00"))
    snap_at=datetime.fromisoformat(created_at.replace("Z","+00:00"))
    if feed_at.tzinfo is None or snap_at.tzinfo is None or feed_at>snap_at:
        raise ValueError("Invalid scoreboard observation time")
    if (snap_at-feed_at).total_seconds()>300:
        raise ValueError("Scoreboard older than five minutes; refresh before predictions")
    # Preserve the signed-by-digest snapshot body unchanged.
    return generate(history,fixtures,created_at)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True,help="Validated completed-game ledger JSON")
    p.add_argument("--date",required=True,help="NBA scoreboard date YYYY-MM-DD")
    p.add_argument("--output",required=True,help="Create-only immutable JSON snapshot")
    x=p.parse_args()
    now=datetime.now(timezone.utc).isoformat()
    scoreboard=fetch_day(x.date,now)
    history=json.loads(Path(x.history).read_text())
    snapshot=run(history,scoreboard,now)
    target=Path(x.output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x") as f:json.dump(snapshot,f,indent=2)
    print(json.dumps({"date":x.date,"games":len(snapshot["predictions"]),
        "created_at_utc":snapshot["created_at_utc"],
        "status":"snapshot_created; candidate predictions not calibrated",
        "output":str(target)},indent=2))
if __name__=="__main__":main()
