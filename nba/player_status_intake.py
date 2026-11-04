"""Map timestamped ESPN injury claims to current player IDs without upgrading reliability.

Only unambiguous team+normalized-name matches are passed to roster resolver.
Unknown players and conflicting claims are reported. Missing injury reports do
not certify that unmentioned players are available.
"""
import argparse,json,unicodedata
from pathlib import Path
from datetime import datetime,timezone
from team_identity import same_team

def normalize(s):
 return " ".join("".join(c for c in unicodedata.normalize("NFKD",str(s).casefold()) if not unicodedata.combining(c)).split())
def utc(s):
 try:
  d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
  return d.astimezone(timezone.utc) if d.tzinfo else None
 except (ValueError,TypeError):return None
def status(s):
 t=normalize(s)
 if t in ("out","inactive","suspended","ruled out"):return "out"
 if t in ("questionable","doubtful","day-to-day","day to day"):return "questionable"
 if t in ("probable",):return "probable"
 # Do not infer active from absence of an injury entry.
 return None
def reconcile(snapshot,roster,sporting):
 digest=snapshot["content_sha256"]
 if roster.get("snapshot_sha256")!=digest:raise ValueError("Roster snapshot mismatch")
 output={};unknown=[];conflicts=[]
 for game in snapshot["predictions"]:
  gid=str(game["game_id"]);tip=utc(game["tipoff_utc"]);per_team={}
  evidence=sporting.get("games",{}).get(gid,{}).get("supplementary_injury_observations",{})
  observed=utc(evidence.get("observed_at_utc"))
  rows=evidence.get("items",[])
  if not isinstance(rows,list):rows=[]
  source=evidence.get("source")
  valid_time=bool(tip and observed and observed<tip)
  for team in (game["home_team"],game["away_team"]):
   members=roster.get("games",{}).get(gid,{}).get("teams",{}).get(team,{}).get("players",[])
   by_name={}
   for p in members:
    if p.get("player_id") and p.get("player"):
     by_name.setdefault(normalize(p["player"]),[]).append(str(p["player_id"]))
   member_ids={str(p["player_id"]) for p in members if p.get("player_id")}
   claims={}
   for row in rows if valid_time and source else []:
    if not same_team(row.get("team"),team):continue
    reported=utc(row.get("reported_at_utc")) if row.get("reported_at_utc") else None
    if row.get("reported_at_utc") and (not reported or reported>observed):continue
    state=status(row.get("status"))
    if state is None:continue
    source_id=str(row.get("player_id") or "")
    ids=[source_id] if source_id and source_id in member_ids else by_name.get(normalize(row.get("player")),[]) if not source_id else []
    if len(ids)!=1:
     unknown.append({"game_id":gid,"team":team,"player":row.get("player"),"reason":"not_unique_roster_match"})
     continue
    pid=ids[0]
    claims.setdefault(pid,[]).append({"player_id":pid,"status":state,
     "source_url":source,"observed_at_utc":evidence["observed_at_utc"],
     "identity_match":"provider_id" if source_id else "unique_normalized_name",
     "reported_at_utc":row.get("reported_at_utc"),
     "confidence":"supplementary_espn_injury_claim_not_official"})
   for pid,observations in claims.items():
    if len({x["status"] for x in observations})>1:
     conflicts.append({"game_id":gid,"team":team,"player_id":pid})
   per_team[team]=[item for values in claims.values() for item in values]
  output[gid]={"teams":per_team}
 return {"snapshot_sha256":digest,"games":output,"unmatched_claims":unknown,
  "conflicts":conflicts,"source_reliability":"supplementary_not_official",
  "does_not_confirm_active_players":True,"no_odds_input":True}
def main():
 p=argparse.ArgumentParser()
 for name in ("snapshot","roster","sporting","output"):p.add_argument("--"+name,required=True)
 args=p.parse_args();snap=json.loads(Path(args.snapshot).read_text())
 def read(path):return json.loads(Path(path).read_text()) if Path(path).exists() else {}
 report=reconcile(snap,read(args.roster),read(args.sporting))
 out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2))
 print(json.dumps({"games":len(report["games"]),"matched_status_claims":sum(len(x) for g in report["games"].values() for x in g["teams"].values()),"unmatched":len(report["unmatched_claims"])}))
if __name__=="__main__":main()
