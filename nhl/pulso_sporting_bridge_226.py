"""Evidence-only sporting bridge. Observations are not confirmation or model features."""
import argparse,json
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

def bridge(report,crosswalk,rosters):
 asof=parse_utc(report["generated_at_utc"])
 source_time=crosswalk.get("retrieved_at")
 if source_time and parse_utc(source_time)>asof:raise ValueError("Goalie source arrives after capture")
 roster_rows=rosters.get("rosters",[])
 if isinstance(roster_rows,dict):roster_rows=list(roster_rows.values())
 roster_by_team={r["team"]:r for r in roster_rows if isinstance(r,dict) and r.get("team")}
 observations=crosswalk.get("observations",[])
 games={}
 for fixture in report["games"]:
  gid=str(fixture["game_id"]);start=parse_utc(fixture["start_utc"])
  if asof>=start:raise ValueError("Post-start fixture: "+gid)
  teams={}
  for team in (fixture["home"],fixture["away"]):
   r=roster_by_team.get(team)
   roster_ok=bool(r and r.get("as_of") and parse_utc(r["as_of"])<=asof)
   obs=[o for o in observations if o.get("team")==team and o.get("matchup_verified") is True and
        (str(o.get("game_id"))==gid or (o.get("game_id") is None and len(report["games"])==1))]
   # Missing fixture ID in a multiple-game capture is not safe to attribute.
   obs=[o for o in obs if o.get("game_id") is not None or len(report["games"])==1]
   usable=[o for o in obs if o.get("usable_pregame_identity") is True and o.get("nhl_player_id") is not None]
   teams[team]={"roster_identity_available":roster_ok,
    "provider_goalie_observation_count":len(obs),
    "provider_goalie_identity_linked":len(usable)==1,
    "provider_goalie_id_observed":usable[0]["nhl_player_id"] if len(usable)==1 else None,
    "goalie_confirmed_independently":False,
    "goalie_historical_rating":None,"skater_crs":None,"availability_delta":None,
    "defensive_unit_rating":None,"pp_bayes":None,"pk_bayes":None,"rest_days":None,
    "source_status":"provider_observation_only" if obs else "no_goalie_evidence"}
  games[gid]={"game_id":gid,"home":fixture["home"],"away":fixture["away"],
   "start_utc":fixture["start_utc"],"as_of":report["generated_at_utc"],
   "teams":teams,"official_probabilities":None}
 return {"kind":"sporting_source_bridge","as_of":report["generated_at_utc"],
  "source_url":crosswalk.get("source_url"),"games":games,"odds_used":False,
  "source_attestation_verified":False,"model_trained":False}
def main():
 p=argparse.ArgumentParser()
 for k in ("report","crosswalk","rosters","out"):p.add_argument("--"+k,required=True)
 a=p.parse_args();read=lambda k:json.loads(Path(getattr(a,k)).read_text())
 result=bridge(read("report"),read("crosswalk"),read("rosters"))
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({"fixture_count":len(result["games"]),"verified_model_ready":0}))
if __name__=="__main__":main()
