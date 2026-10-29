"""Audit NHL.com projected skater identity coverage for independently attested fixtures.

Never automatically attest editorial date or infer starters from team names.
No CRS/goal rate without complete verified as-of and independent availability.
"""
import argparse,json
from pathlib import Path
from nhl.nhlcom_lineup_identity import resolve

def evaluate(capture,rosters,fixture):
  linked=resolve(capture,rosters,fixture)  # independently attested fixture required
  teams=[]
  for team in linked["teams"]:
    rows=team["projected_skaters"]
    ids=[str(x["player_id"]) for x in rows]
    forwards=sum(x["position_group"]=="forward" for x in rows)
    defense=sum(x["position_group"]=="defense" for x in rows)
    complete=len(rows)==18 and forwards==12 and defense==6 and not team["unresolved_skaters"] and len(set(ids))==18
    teams.append({"team":team["team"],"projected_skater_ids":ids,
      "forward_count":forwards,"defense_count":defense,"unresolved_names":team["unresolved_skaters"],
      "projected_18_skater_identity_complete":complete,
      "independently_verified_player_availability":False,
      "starter_goalie_confirmed":False})
  return {"game_id":linked["game_id"],"teams":teams,"source_url":linked["source_url"],
    "captured_at":linked["source_captured_at"],"editorial_fixture_attestation_required":True,
    "projection_identity_coverage_complete":all(x["projected_18_skater_identity_complete"] for x in teams),
    "available_for_numeric_crs":False,"full_team_predictions_eligible":False,
    "probabilities":None,
    "blockers":["injury_and_scratch_status_unverified","starter_goalies_not_independently_confirmed",
       "historical_asof_player_value_and_full_crs_not_trained"],
    "odds_used":False}
def main():
 p=argparse.ArgumentParser()
 for name in ("capture","rosters","fixture","out"):p.add_argument("--"+name,required=True)
 a=p.parse_args();result=evaluate(*[json.loads(Path(getattr(a,x)).read_text()) for x in ("capture","rosters","fixture")])
 output=Path(a.out);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2))
 print(json.dumps({"game_id":result["game_id"],"coverage_complete":result["projection_identity_coverage_complete"],"eligible":False}))
if __name__=="__main__":main()
