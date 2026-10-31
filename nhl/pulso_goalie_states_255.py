"""Fixture-specific goalie confirmation state; absence is not a data error."""
import argparse,json
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def classify(report,identity):
 at=parse_utc(report["generated_at_utc"])
 if identity.get("kind")!="nhl_fixture_identity_gate_248" or parse_utc(identity["as_of_utc"])!=at:
  raise ValueError("Invalid identity source or as-of")
 byid={str(g["game_id"]):g for g in identity["games"]}
 if len(byid)!=len(identity["games"]):raise ValueError("Duplicate fixtures")
 games=[];counts={"confirmed":0,"probable":0,"unconfirmed":0,"source_error":0}
 for f in report["games"]:
  g=byid.get(str(f["game_id"]))
  if not g or (g["home"],g["away"])!=(f["home"],f["away"]):raise ValueError("Fixture mismatch")
  start=parse_utc(f["start_utc"])
  if at>=start:raise ValueError("Not pregame")
  teams={}
  for team in (f["home"],f["away"]):
   row=g["teams"].get(team)
   if row is None:raise ValueError("Team missing from fixture")
   blockers=row.get("blockers",[])
   pid=row.get("source_goalie_player_id")
   if row.get("independent_goalie_confirmation") is True:
    state="confirmed" if type(pid) is int else "source_error"
   elif type(pid) is int:
    state="probable"
   elif any(x in blockers for x in ("missing_official_roster_identity_pool","no_unique_fixture_linked_goalie_player_id")):
    # Identity crosswalk failure is not automatically an API outage or a declaration.
    state="unconfirmed"
   else:state="unconfirmed"
   counts[state]+=1
   teams[team]={"state":state,"candidate_player_id":pid,"independently_confirmed":state=="confirmed",
    "time_to_puck_drop_minutes":int((start-at).total_seconds()//60),
    "normal_pregame_uncertainty":state in ("probable","unconfirmed"),
    "auto_pass":False,"ml_penalty":None,
    "note":"Provider-confirmed is not independently confirmed" if row.get("source_goalie_status")=="source_reported_confirmed" and state!="confirmed" else None}
  games.append({"game_id":str(f["game_id"]),"home":f["home"],"away":f["away"],"teams":teams})
 return {"kind":"nhl_goalie_confirmation_states_255","as_of_utc":report["generated_at_utc"],
  "games":games,"counts":counts,"official_predictions":0,"odds_used":False,
  "note":"Confirmation is expected to evolve before puck drop. No completeness target or auto-PASS."}
def main():
 p=argparse.ArgumentParser()
 for k in ("report","identity","out"):p.add_argument("--"+k,required=True)
 a=p.parse_args()
 result=classify(json.loads(Path(a.report).read_text()),json.loads(Path(a.identity).read_text()))
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2))
 print(json.dumps(result["counts"]))
if __name__=="__main__":main()
