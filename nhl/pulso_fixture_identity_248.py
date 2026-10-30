"""#248: auditable NHL fixture-specific identity corroboration.

Roster membership is a candidate identity set, NOT a verified lineup. NHL.com
editorial lineup blocks are only usable for names after publication date and
fixture mapping have been attested. ESPN goalie 'confirmed' is provider reported
and never independent NHL starter confirmation.
"""
import argparse,json,unicodedata
from collections import defaultdict
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def normalize(name):
 return " ".join("".join(c for c in unicodedata.normalize("NFKD",name.casefold())
                    if not unicodedata.combining(c)).split())
def reconcile(report,rosters,goalies,editorial):
 issued=parse_utc(report["generated_at_utc"])
 if report.get("data_kind")!="source_readiness_only" or report.get("official_predictions")!=0:
  raise ValueError("Unpromoted pregame report required")
 rows=rosters.get("rosters",[])
 if not isinstance(rows,list):raise ValueError("Invalid current rosters")
 byteam={}
 for rec in rows:
  team=rec.get("team")
  if team in byteam:raise ValueError("Duplicate team roster")
  byteam[team]=rec
 obs=goalies.get("observations",[])
 if not isinstance(obs,list):raise ValueError("Invalid goalie observations")
 editorial_ob=editorial.get("observation") or {}
 editorial_verified=bool(editorial.get("fixture_attested") is True and
   editorial_ob.get("fixture_mapping_verified") is True and
   editorial_ob.get("publication_date_verified") is True and
   editorial_ob.get("player_ids_resolved") is True)
 games=[]
 for f in report["games"]:
  start=parse_utc(f["start_utc"])
  if issued>=start:raise ValueError("Fixture started")
  teams={}
  for team in (f["home"],f["away"]):
   rec=byteam.get(team)
   issues=[]
   name_map=defaultdict(list)
   if rec:
    if not rec.get("source_url","").startswith("https://") or parse_utc(rec["as_of"])>issued:
     raise ValueError("Late or unattributed NHL roster")
    for p in rec.get("players",[]):
     if type(p.get("player_id")) is not int:raise ValueError("Invalid NHL player ID")
     name_map[normalize(p.get("full_name",""))].append(p["player_id"])
   else:issues.append("missing_official_roster_identity_pool")
   if not editorial_verified:issues.append("editorial_lineup_not_fixture_attested_or_player_ids_unresolved")
   matching=[g for g in obs if g.get("team")==team and str(g.get("game_id"))==str(f["game_id"])
      and g.get("matchup_verified") is True]
   valid=[]
   for g in matching:
    if g.get("usable_pregame_identity") is not True:continue
    pid=g.get("nhl_player_id")
    if type(pid) is not int or not rec or pid not in {p["player_id"] for p in rec["players"]}:continue
    valid.append(g)
   if len(valid)!=1:issues.append("no_unique_fixture_linked_goalie_player_id")
   source_confirmed=(len(valid)==1 and valid[0].get("goalie_status")=="confirmed")
   if not source_confirmed:issues.append("goalie_not_source_reported_confirmed")
   if not goalie.get("independent_starter_confirmation",False):
    issues.append("goalie_not_independently_confirmed")
   teams[team]={"roster_candidate_count":sum(len(v) for v in name_map.values()),
     "unique_roster_name_matches":sum(len(v)==1 for v in name_map.values()),
     "source_goalie_player_id":valid[0]["nhl_player_id"] if len(valid)==1 else None,
     "source_goalie_status":"source_reported_confirmed" if source_confirmed else "unverified",
     "independent_goalie_confirmation":False,
     "editorial_lineup_identity_verified":False,
     "expected_lineup":None,
     "verified_lineup_history_package":None,
     "blockers":issues}
  games.append({"game_id":str(f["game_id"]),"home":f["home"],"away":f["away"],
      "start_utc":f["start_utc"],"teams":teams})
 return {"kind":"nhl_fixture_identity_gate_248","as_of_utc":report["generated_at_utc"],
  "games":games,"source_lineups_verified":0,"independent_goalies_confirmed":0,
  "official_predictions":0,"odds_used":False,
  "notes":"Only identity corroboration, not source-attested full lineups or player history. Never manufacture 247 packages."}
def main():
 p=argparse.ArgumentParser()
 for name in ("report","rosters","goalies","editorial","out"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 read=lambda x:json.loads(Path(getattr(a,x)).read_text())
 out=reconcile(read("report"),read("rosters"),read("goalies"),read("editorial"))
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(out,indent=2))
 print(json.dumps({"fixtures":len(out["games"]),"verified_lineups":0,"confirmed_goalies":0}))
if __name__=="__main__":main()
