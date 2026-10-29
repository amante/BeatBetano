"""Join independently captured ESPN goalies, official schedule and NHL roster by ID.

Outputs retrospective/pregame evidence, not an official or validated CRS signal.
"""
import argparse,json
from pathlib import Path
from collections import Counter
try:
 from nhl.espn_goalie_provider_capture import reconcile
 from nhl.roster_aware_units import timepoint
except ModuleNotFoundError:
 from espn_goalie_provider_capture import reconcile
 from roster_aware_units import timepoint

def summarize(espn,schedule,rosters):
 result=reconcile(espn,rosters,schedule)
 counts=Counter()
 for row in result["observations"]:
  counts["observations"]+=1
  if row["goalie_status"]=="confirmed":counts["source_confirmed"]+=1
  if row["nhl_player_id"] is not None:counts["identity_linked"]+=1
  if row["matchup_verified"]:counts["fixture_linked"]+=1
  if row["usable_pregame_identity"]:counts["pregame_identity_usable"]+=1
  for error in row["validation_errors"]:counts["error_"+error]+=1
 return {"source_url":espn["source"]["source_url"],"retrieved_at":espn["source"]["retrieved_at"],
  "summary":dict(counts),"observations":result["observations"],
  "official_lineup_confirmed":False,"full_crs_eligible":False,"odds_used":False,
  "note":"Independent roster identity + official fixture verified separately. ESPN starter statuses remain provider assertions; no full CRS."}

def main():
 p=argparse.ArgumentParser()
 for key in ("espn","schedule","rosters","output"):p.add_argument("--"+key,required=True)
 a=p.parse_args()
 result=summarize(json.loads(Path(a.espn).read_text()),
    json.loads(Path(a.schedule).read_text()),json.loads(Path(a.rosters).read_text()))
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
 print(json.dumps(result["summary"],indent=2))
if __name__=="__main__":main()
