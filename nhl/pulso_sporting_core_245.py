"""#245: execution-level NHL sporting contract, no silent substitution.

Integrates captured goalie/roster evidence, quantitatively verified CRS/goalie/ST
signals, contextual rivalry and historical roster-delta research. It reports
the actual contribution chain; zero model coefficients are applied until fitted.
"""
import argparse,json,math
from pathlib import Path
from nhl.module_audit import context as rivalry_context
from nhl.pulso_pregame_v7 import parse_utc
from nhl.pulso_quantitative_signals_227 import compute as verified_signals

MODULES={
 "crs":"current roster strength and independently verified player availability",
 "availability_delta":"lineup baseline-to-expected player replacement impact",
 "offensive_units":"top6 middle6 bottom6",
 "defensive_units":"top4_d depth_d",
 "goalie_daily":"identified starting goalie, prior form and fatigue",
 "special_teams":"bayesian power-play penalty-kill",
 "venue_rest_travel":"home ice, rest, travel and back-to-back",
 "division_rivalry":"division, rivalry tier and tactical familiarity",
 "quality_momentum":"opponent-adjusted recent quality and recovery",
 "sporting_ml":"fitted probabilities using every verified active module",
 "regulation":"fitted regulation time probabilities",
 "three_goal_lead":"fitted first-to-plus3 and both-side three-goal probabilities",
 "rescue_dual_fuerte":"market-specific, validated decision rules"
}
UNITS=("top6","middle6","bottom6","top4_d","depth_d")
def finite(x):
 return type(x) in (int,float) and math.isfinite(x)
def contribution(name,source,source_asof,observed,applied=False,effect=None,blocker=None):
 if applied and (not finite(effect) or source_asof is None or source is None):
  raise ValueError("An applied module must have source, timestamp and numerical effect")
 if not applied and effect is not None:raise ValueError("Blocked modules cannot claim contributions")
 return {"module":name,"source":source,"as_of":source_asof,"observed":observed,
         "applied_to_sporting_probability":applied,"probability_delta":effect,
         "blocker":blocker if not applied else None}
def integrate(report,bridge,packages,unit_research=None,live_sporting=None,individual_evidence=None):
 if report.get("data_kind")!="source_readiness_only" or report.get("official_predictions")!=0:
  raise ValueError("Raw pregame source report required")
 asof=parse_utc(report["generated_at_utc"])
 if bridge.get("kind")!="sporting_source_bridge" or parse_utc(bridge["as_of"])!=asof:
  raise ValueError("Bridge and capture timestamps disagree")
 if live_sporting is not None and (live_sporting.get('kind')!='nhl_live_sporting_observations_246' or parse_utc(live_sporting['observed_at_utc'])!=asof):
  raise ValueError('Live sporting timestamp mismatch')
 live_by_id={str(g['game_id']):g for g in live_sporting.get('games',[])} if live_sporting else {}
 if individual_evidence is not None and (individual_evidence.get('kind')!='nhl_individual_player_goalie_evidence_247' or parse_utc(individual_evidence['as_of_utc'])!=asof):
  raise ValueError('Individual evidence timestamp mismatch')
 individual_by_id={str(g['game_id']):g for g in individual_evidence.get('games',[])} if individual_evidence else {}
 quant=verified_signals(bridge,packages)
 seen=set();out=[]
 for fixture in report["games"]:
  gid=str(fixture["game_id"])
  if gid in seen:raise ValueError("Duplicate fixture")
  seen.add(gid)
  if gid not in bridge["games"]:raise ValueError("Missing fixture in bridge")
  bg=bridge["games"][gid]
  if any(fixture[k]!=bg[k] for k in ("home","away","start_utc")):
   raise ValueError("Cross-source fixture mismatch")
  start=parse_utc(fixture["start_utc"])
  if asof>=start:raise ValueError("Fixture is not pregame")
  sources={};details={}
  q=quant["games"][gid] if "games" in quant else quant[gid]
  for team in (fixture["home"],fixture["away"]):
   src=bg["teams"][team];sig=q["teams"][team]
   details[team]={"roster_identity_available":src["roster_identity_available"],
     "goalie_observed_id":src["provider_goalie_id_observed"],
     "goalie_independently_confirmed":src["goalie_confirmed_independently"],
     "verified_signals":sig["signals"],"data_issues":sig["issues"]}
  # Observable evidence is NOT necessarily applicable to a calibrated effect.
  def both(key):
   return all(key in details[t]["verified_signals"] for t in details)
  units=(unit_research or {}).get(gid,{})
  if units and not isinstance(units,dict):raise ValueError("Malformed units")
  unit_obs=units.get("units",{})
  if unit_obs and not isinstance(unit_obs,dict):raise ValueError("Malformed unit observations")
  if unit_obs and set(unit_obs)-set(UNITS):raise ValueError("Unrecognized unit")
  current=live_by_id.get(gid)
  if current and any(current[k]!=fixture[k] for k in ('home','away','start_utc')):raise ValueError('Live fixture mismatch')
  current_sides=current['sides'] if current else {}
  for team in details:
   details[team]['official_prior_day_team_form']=current_sides.get(team)
  individual=individual_by_id.get(gid)
  if individual and (individual["home"]!=fixture["home"] or individual["away"]!=fixture["away"]):raise ValueError("Individual fixture mismatch")
  for team in details:
   details[team]["individual_player_goalie_evidence"]=individual["teams"].get(team) if individual else None
  ctx=rivalry_context(fixture["home"],fixture["away"])
  annotations={
   "crs":{"observed":both("crs"),"blocker":"no fitted and complete roster strength valuation"},
   "availability_delta":{"observed":both("crs"),"blocker":"independent verified matchup replacement effect not calibrated"},
   "offensive_units":{"observed":all(k in unit_obs for k in UNITS[:3]),"blocker":"verified unit deployment and calibrated contribution missing"},
   "defensive_units":{"observed":all(k in unit_obs for k in UNITS[3:]),"blocker":"defensive ratings and deployment not fitted"},
   "goalie_daily":{"observed":both("goalie"),"blocker":"goalie identity, fatigue/GSAx and fitted delta incomplete"},
   "special_teams":{"observed":both("special_teams"),"blocker":"fitted opponent PP/PK matchup coefficient missing"},
   "venue_rest_travel":{"observed":False,"blocker":"complete verified rest/travel/B2B observations and fitted effects missing"},
   "division_rivalry":{"observed":ctx["divisional"] or ctx["rivalry"],"blocker":"rivalry contextual probability coefficients uncalibrated"},
   "quality_momentum":{"observed":False,"blocker":"opponent-adjusted quality momentum coefficient not fitted"},
   "sporting_ml":{"observed":False,"blocker":"no validated joint sporting ML weights"},
   "regulation":{"observed":False,"blocker":"regulation scoring/draw process not fitted"},
   "three_goal_lead":{"observed":False,"blocker":"independent two-sided 3GLP process not fitted"},
   "rescue_dual_fuerte":{"observed":False,"blocker":"market-specific gates not validated"}}
  modules={key:contribution(key,"pregame_source_bridge+quantitative_signals_227" if value["observed"] else None,
    report["generated_at_utc"] if value["observed"] else None,value["observed"],
    blocker=value["blocker"]) for key,value in annotations.items()}
  if set(modules)!=set(MODULES):raise AssertionError("Module contract incomplete")
  out.append({"game_id":gid,"home":fixture["home"],"away":fixture["away"],
    "start_utc":fixture["start_utc"],"as_of_utc":report["generated_at_utc"],
    "module_manifest":modules,"teams":details,"context":ctx,"unit_research":unit_obs,
    "official_prior_day_team_form_source":live_sporting.get("source_url") if live_sporting else None,
    "sporting_goal_rates":None,"sporting_probabilities":None,"official":False,
    "sporting_model_status":"blocked_missing_verified_fitted_effects",
    "no_silent_fallback":True,"odds_used":False})
 return {"kind":"nhl_sporting_core_integrity_245","generated_at_utc":report["generated_at_utc"],
  "module_contract_version":"nhl-2026-27-original-recovery-v1",
  "model_status":"integrated_evidence_not_calibrated",
  "official_predictions":0,"games":out,"module_count":len(MODULES),
  "forecast_promotion_allowed":False,"odds_used":False,
  "warning":"This is a real integration/audit of evidence, not the completed sporting predictor. Statistical auxiliary forecasts are never substituted."}
def main():
 p=argparse.ArgumentParser()
 for x in ("report","bridge","packages","out"):p.add_argument("--"+x,required=True)
 p.add_argument("--unit-research")
 p.add_argument("--live-sporting")
 p.add_argument("--individual-evidence")
 a=p.parse_args()
 load=lambda path:json.loads(Path(path).read_text())
 result=integrate(load(a.report),load(a.bridge),load(a.packages),load(a.unit_research) if a.unit_research else None,load(a.live_sporting) if a.live_sporting else None,load(a.individual_evidence) if a.individual_evidence else None)
 dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({"fixtures":len(result["games"]),"modules":result["module_count"],"official_predictions":0}))
if __name__=="__main__":main()
