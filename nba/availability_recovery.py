"""Conservative alternate ESPN game-summary injury recovery when injury feed is empty.

A recovered ESPN claim remains supplementary evidence, never an official NBA
injury confirmation, roster impact, confirmed starter or betting adjustment.
"""
import argparse,json
from pathlib import Path
from datetime import datetime,timezone

def utc(x):
 d=datetime.fromisoformat(str(x).replace("Z","+00:00"))
 if d.tzinfo is None:raise ValueError("Timezone required")
 return d.astimezone(timezone.utc)

def recover(snapshot,sporting,preview):
 if preview.get("snapshot_sha256")!=snapshot.get("content_sha256"):
  raise ValueError("ESPN preview snapshot mismatch")
 out={}
 for g in snapshot["predictions"]:
  gid=str(g["game_id"]);tip=utc(g["tipoff_utc"])
  feed=sporting.get("games",{}).get(gid,{}).get("supplementary_injury_observations",{})
  feed_items=feed.get("items",[]) if isinstance(feed,dict) else []
  feed_time=feed.get("observed_at_utc") if isinstance(feed,dict) else None
  timely_feed=False
  try:timely_feed=bool(feed_time and utc(feed_time)<tip)
  except ValueError:pass
  p=preview.get("games",{}).get(gid,{})
  timely_preview=False
  try:
   timely_preview=(p.get("is_pregame_evidence") is True
      and utc(p["observed_at_utc"])<tip)
  except (KeyError,TypeError,ValueError):pass
  recovered=[]
  if timely_preview and not (timely_feed and feed_items):
   for row in p.get("injury_observations",[]):
    if not isinstance(row,dict) or not row.get("player"):continue
    recovered.append({"player":row["player"],"reported_status":row.get("status"),
     "team":None,"source":"ESPN game summary","source_url":p.get("source_url"),
     "observed_at_utc":p["observed_at_utc"],"official_status_verified":False,
     "team_identity_verified":False})
  out[gid]={"home_team":g["home_team"],"away_team":g["away_team"],
    "feed_claim_count":len(feed_items) if timely_feed else 0,
    "recovered_summary_claims":recovered,"recovered_count":len(recovered),
    "missing_official_report":True,"starting_fives_confirmed":False,
    "next_required_evidence":["official_injury_report","verified_player_team_status",
      "confirmed_starting_fives"],"probability_adjustment_authorized":False}
 return {"snapshot_sha256":snapshot["content_sha256"],"games":out,
  "note":"Summary claims are unverified team-unassigned observations only; no source stacking as independent corroboration."}
def main():
 p=argparse.ArgumentParser()
 for name in ("snapshot","sporting","preview","output"):p.add_argument("--"+name,required=True)
 a=p.parse_args();read=lambda k:json.loads(Path(getattr(a,k)).read_text())
 r=recover(read("snapshot"),read("sporting"),read("preview"))
 dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(r,indent=2))
 print(json.dumps({"games":len(r["games"]),"supplementary_recovered":sum(x["recovered_count"] for x in r["games"].values()),"official_confirmations":0}))
if __name__=="__main__":main()
