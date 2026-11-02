"""Pregame goalie-conditioned scenario matrix; no invented probabilities."""
import argparse,json,itertools
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

MARKETS=("ml_home","ml_away","rt_home","rt_draw","rt_away",
 "three_goal_lead_home","three_goal_lead_away","first_plus3_home",
 "first_plus3_away","rescue_home","rescue_away")

def editorial_candidates(report,rosters,raw):
 """Both published goalies, resolved to roster IDs; never infer a starter."""
 from nhl.match_context import editorial
 from nhl.nhlcom_lineup_identity import normalized
 from nhl.pulso_goalie_multisource_257 import TEAM_NAMES
 from zoneinfo import ZoneInfo
 at=parse_utc(report['generated_at_utc'])
 try:published,blocks=editorial(raw,at)
 except (ValueError,KeyError,UnicodeError):return {},{'article':'missing_or_unverified_date'}
 by_team={r['team']:r for r in rosters};out={};issues={}
 if len(by_team)!=len(rosters):raise ValueError('Duplicate roster')
 for f in report['games']:
  gid=str(f['game_id']);sides={};local=parse_utc(f['start_utc']).astimezone(ZoneInfo('America/Santiago')).date()
  if published.astimezone(ZoneInfo('America/Santiago')).date()!=local:continue
  for team in (f['home'],f['away']):
   matches=[b for name,b in blocks.items() if normalized(TEAM_NAMES[team]).endswith(' '+normalized(name))]
   if len(matches)!=1:break
   roster=by_team.get(team)
   if not roster or parse_utc(roster['as_of'])>at:break
   names=matches[0]['goalies'];players=roster.get('players',[]);resolved=[]
   for name in names:
    options=[p for p in players if p.get('position_group')=='goalie' and normalized(p.get('full_name',''))==normalized(name)]
    if len(options)!=1:
     issues.setdefault(gid+':'+team,[]).append(name);continue
    resolved.append({'player_id':options[0]['player_id'],'name':name,'source':'NHL.com projected lineup/NHL roster','status':'projected'})
   sides[team]=resolved
  if len(sides)==2:out[gid]=sides
 return out,issues

def build(report,identity,external,forecasts=None,editorial_observations=None,editorial_issues=None):
 at=parse_utc(report["generated_at_utc"])
 if identity.get("kind")!="nhl_fixture_identity_gate_248" or parse_utc(identity["as_of_utc"])!=at:raise ValueError("Bad identity evidence")
 if external.get("kind")!="nhl_external_goalie_observations_257" or parse_utc(external["as_of_utc"])!=at:raise ValueError("Bad provider evidence")
 ig={str(g["game_id"]):g for g in identity["games"]}
 eg={}
 for ob in external["observations"]:
  key=(str(ob["game_id"]),ob["team"])
  if key in eg:raise ValueError("Ambiguous external candidate")
  eg[key]=ob
 games=[]
 for f in report["games"]:
  gid=str(f["game_id"]);g=ig.get(gid)
  if g is None or (g["home"],g["away"])!=(f["home"],f["away"]):raise ValueError("Fixture mismatch")
  if at>=parse_utc(f["start_utc"]):raise ValueError("Fixture not pregame")
  candidates={}
  for team in (f["home"],f["away"]):
   r=g["teams"][team];items=[]
   pid=r.get("source_goalie_player_id")
   if type(pid) is int:items.append({"player_id":pid,"name":r.get("source_goalie_name") or "Nombre no disponible","source":"ESPN/NHL roster","status":"candidate"})
   e=eg.get((gid,team))
   if e:
    ep=e["player_id"]
    if type(ep) is not int:raise ValueError("Invalid external player ID")
    if not any(v["player_id"]==ep for v in items):
     items.append({"player_id":ep,"name":e["name"],"source":"Daily Faceoff/NHL roster","status":e["provider_status"]})
    else:
     next(v for v in items if v["player_id"]==ep)["status"]=e["provider_status"]
   for candidate in (editorial_observations or {}).get(gid,{}).get(team,[]):
    if type(candidate.get('player_id')) is not int or candidate['player_id']<=0:raise ValueError('Invalid projected goalie ID')
    if not any(v['player_id']==candidate['player_id'] for v in items):items.append(candidate)
   candidates[team]=items
  scenarios=[]
  for h,a in itertools.product(candidates[f["home"]],candidates[f["away"]]):
   scenarios.append({"home_goalie":h,"away_goalie":a,
    "probabilities":{m:None for m in MARKETS},"prediction_status":"awaiting_fitted_sporting_model",
    "auto_pass":False})
  missing=[team for team in (f["home"],f["away"]) if not candidates[team]]
  games.append({"game_id":gid,"home":f["home"],"away":f["away"],"goalie_candidates":candidates,
   "scenarios":scenarios,"scenario_count":len(scenarios),
   "scenario_status":"blocked_missing_goalie_identity" if missing else "pairings_ready",
   "missing_goalie_teams":missing,"unresolved_editorial_candidates":{team:(editorial_issues or {}).get(gid+":"+team,[]) for team in (f["home"],f["away"])}})
 return {"kind":"nhl_goalie_conditional_scenarios_258","as_of_utc":report["generated_at_utc"],
   "games":games,"official_predictions":0,"odds_used":False,
   "fixtures_total":len(games),"fixtures_without_scenarios":sum(g["scenario_count"]==0 for g in games),
   "fixture_coverage_complete":all(g["scenario_count"]>0 for g in games),
   "note":"Precomputes exact goalie pairings; percentages remain unavailable until validated calibrated sporting model."}
def main():
 p=argparse.ArgumentParser()
 for x in ("report","identity","external","out"):p.add_argument("--"+x,required=True)
 p.add_argument("--rosters");p.add_argument("--editorial-raw")
 a=p.parse_args()
 report,identity,external=[json.loads(Path(getattr(a,k)).read_text()) for k in ("report","identity","external")]
 if bool(a.rosters)!=bool(a.editorial_raw):p.error('Both roster and raw editorial paths are required')
 projected,issues=editorial_candidates(report,json.loads(Path(a.rosters).read_text())['rosters'],Path(a.editorial_raw).read_bytes()) if a.rosters else ({},{})
 x=build(report,identity,external,editorial_observations=projected,editorial_issues=issues)
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(x,indent=2))
 for g in x["games"]:
  print(f'{g["away"]}@{g["home"]}: {g["scenario_count"]} combinations')
  for sc in g["scenarios"]:
   print(f'  {sc["home_goalie"]["name"]} vs {sc["away_goalie"]["name"]}: ML pending calibration')
if __name__=="__main__":main()
