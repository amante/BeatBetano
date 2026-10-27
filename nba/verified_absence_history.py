"""Point-in-time NBA absence ledger: join pretip status evidence to postgame minutes.

Claims are accepted as VERIFIED only from explicitly certified upstream reports;
postgame DNP and missing injury entries never imply a pregame OUT or healthy.
"""
import argparse,json
from pathlib import Path
from datetime import datetime,timezone
def ts(value):
 try:
  d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
  return d.astimezone(timezone.utc) if d.tzinfo else None
 except (ValueError,TypeError):return None
def build(events,observations,boxscores):
 by_event={}
 for e in events:
  gid=str(e["game_id"])
  if gid in by_event:raise ValueError("Duplicate event")
  by_event[gid]=e
 by_box={}
 for b in boxscores:
  gid=str(b.get("game_id"))
  if gid in by_box:raise ValueError("Duplicate boxscore")
  by_box[gid]=b
 out=[];rejects=[]
 for (gid,team),claims in sorted(_group(observations).items()):
  e=by_event.get(gid);box=by_box.get(gid)
  if not e or not box or team not in (e["home_team"],e["away_team"]):
   rejects.append({"game_id":gid,"team":team,"reason":"missing_event_or_box"});continue
  tip=ts(e["tipoff_utc"]);rows=box.get("player_minutes_by_team",{}).get(team)
  if tip is None or not isinstance(rows,dict):
   rejects.append({"game_id":gid,"team":team,"reason":"invalid_tipoff_or_box"});continue
  ids=set();bad=False
  for claim in claims:
   recorded=ts(claim.get("observed_at_utc"));pid=str(claim.get("player_id") or "")
   if not pid or pid in ids or not recorded or recorded>=tip or not claim.get("source_url") or claim.get("official_verified") is not True or claim.get("status") not in ("out","available"):
    bad=True;break
   ids.add(pid)
  if bad:
   rejects.append({"game_id":gid,"team":team,"reason":"claims_not_individually_certified_pretip"});continue
  # Full status coverage is required, not just a list of injured players.
  eligible=set(map(str,box.get("pregame_roster_ids_by_team",{}).get(team,[])))
  if not eligible or ids!=eligible or len(ids)<5:
   rejects.append({"game_id":gid,"team":team,"reason":"incomplete_pregame_player_coverage"});continue
  status={str(c["player_id"]):c["status"] for c in claims}
  invalid=[pid for pid,v in rows.items() if str(pid) in eligible and (type(v) not in (int,float) or v<0 or v>65)]
  if invalid:
   rejects.append({"game_id":gid,"team":team,"reason":"invalid_player_minutes"});continue
  out.append({"game_id":gid,"team":team,"tipoff_utc":e["tipoff_utc"],
   "availability_verified":True,"confirmed_out_player_ids":sorted(pid for pid,st in status.items() if st=="out"),
   "player_minutes":{str(pid):float(v) for pid,v in rows.items() if str(pid) in eligible},
   "observations":[{"player_id":str(c["player_id"]),"status":c["status"],"source_url":c["source_url"],"observed_at_utc":c["observed_at_utc"]} for c in claims]})
 return {"games":out,"rejected":rejects,"no_odds_input":True,
  "note":"Only certified complete pretip status records become verified training games. Postgame outcomes never upgrade source certification."}
def _group(obs):
 out={}
 for c in obs:
  out.setdefault((str(c.get("game_id")),c.get("team")),[]).append(c)
 return out
def main():
 p=argparse.ArgumentParser()
 for n in ("events","statuses","boxscores","output"):p.add_argument("--"+n,required=True)
 a=p.parse_args()
 read=lambda n:json.loads(Path(getattr(a,n)).read_text())
 result=build(read("events"),read("statuses"),read("boxscores"))
 f=Path(a.output);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(result,indent=2))
 print(json.dumps({"certified_team_games":len(result["games"]),"rejected":len(result["rejected"])}))
if __name__=="__main__":main()
