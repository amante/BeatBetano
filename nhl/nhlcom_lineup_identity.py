"""Resolve NHL.com projected names to official roster player IDs conservatively.

Explicit fixture/date attestation required. Editorial notes, injured and
scratched names remain observations, never confirmed scratches or starters.
Unresolved or ambiguous names make numeric/lineup ingestion ineligible.
"""
import argparse,json,re,unicodedata
from pathlib import Path
from datetime import timezone
try:
 from nhl.roster_aware_units import timepoint
except ModuleNotFoundError:
 from roster_aware_units import timepoint

def normalized(s):
 s=unicodedata.normalize("NFKD",s.casefold())
 return re.sub(r"[^a-z0-9 ]","", "".join(c for c in s if not unicodedata.combining(c))).strip()

def resolve(capture,rosters,fixture):
 if not fixture.get("game_id") or not fixture.get("scheduled_start") or not fixture.get("teams"):
  raise ValueError("Fixture with start, game ID and two teams required")
 if len(fixture["teams"])!=2 or len(set(fixture["teams"]))!=2:raise ValueError("Invalid fixture teams")
 if not fixture.get("publication_date_verified") or not fixture.get("fixture_mapping_verified"):
  raise ValueError("Editorial publication date and fixture must be independently verified")
 captured=timepoint(capture["retrieved_at"])
 start=timepoint(fixture["scheduled_start"])
 if captured>=start:raise ValueError("Source capture occurs after scheduled start")
 teams={x["team"]:x for x in rosters}
 result=[]
 for side in fixture["teams"]:
  code=side["code"];label=side["reported_team_name"]
  if code not in teams:raise ValueError("Roster missing for fixture team")
  roster=teams[code]
  if timepoint(roster["as_of"])>captured:raise ValueError("Future roster source relative to editorial capture")
  matches=[b for b in capture["blocks"] if normalized(b["reported_team_name"])==normalized(label)]
  if len(matches)!=1:raise ValueError("Missing or ambiguous lineup team heading")
  block=matches[0]
  names={}
  for p in roster["players"]:
   full=p.get("full_name","").strip()
   if not full:continue
   names.setdefault(normalized(full),[]).append(p)
  resolved=[];unresolved=[];seen=set()
  # Only clear full-name triplets are parsed as line combinations. Do not
  # treat arbitrary prose or standalone goalie lines as confirmed positions.
  for line in block["lines"]:
   parts=[x.strip() for x in re.split(r"\\s+--\\s+|\\s+[–—]\\s+",line)]
   if len(parts) not in (2,3):continue
   group="forward" if len(parts)==3 else "defense"
   for name in parts:
    options=[p for p in names.get(normalized(name),[]) if p["position_group"]==group]
    if len(options)!=1 or options[0]["player_id"] in seen:
     unresolved.append(name);continue
    p=options[0];seen.add(p["player_id"])
    resolved.append({"player_id":p["player_id"],"name":name,"position_group":group,
       "status":"projected","line_text":line})
  result.append({"team":code,"source_team_heading":label,"projected_skaters":resolved,
      "unresolved_skaters":unresolved,"source_scratches_unverified":block["scratched"],
      "source_injuries_unverified":block["injured"],"starting_goalie_confirmed":False,
      "all_expected_players_identified":False})
 return {"game_id":fixture["game_id"],"scheduled_start":fixture["scheduled_start"],
   "source_url":capture["source_url"],"source_captured_at":capture["retrieved_at"],
   "teams":result,"fixture_date_attested":True,"lineup_status":"projected",
   "player_ids_resolved_partially":any(x["projected_skaters"] for x in result),
   "expected_lineup_complete":False,"prediction_eligible":False,
   "odds_used":False,"official_model_promoted":False,
   "reason":"Goalie starter and complete lineup not independently verified; no numeric CRS ingestion."}

def main():
 p=argparse.ArgumentParser()
 for field in ("capture","rosters","fixture","output"):p.add_argument("--"+field,required=True)
 a=p.parse_args();res=resolve(json.loads(Path(a.capture).read_text()),
   json.loads(Path(a.rosters).read_text()),json.loads(Path(a.fixture).read_text()))
 path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(res,indent=2))
 print(json.dumps({"game_id":res["game_id"],"resolved_skaters":sum(len(x["projected_skaters"]) for x in res["teams"]),
  "prediction_eligible":False},indent=2))
if __name__=="__main__":main()
