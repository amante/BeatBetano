"""Integrated NHL pregame RESEARCH assembly; no unsupported official probabilities.

Stage 185: documented skater-unit evidence + availability delta.
Stage 186: sourced prior-date PP/PK observations, fixture context, rivalry metadata.
Stage 187: independent two-sided outcome baseline (not full NHL 14-module model).
No sportsbook odds are consumed, missing inputs remain explicit.
"""
import argparse,json,math
from pathlib import Path
try:
 from nhl.quantitative_roster_delta import compare
 from nhl.roster_aware_units import timepoint
 from nhl.historical_target_walkforward import CATEGORIES,prediction
except ModuleNotFoundError:
 from quantitative_roster_delta import compare
 from roster_aware_units import timepoint
 from historical_target_walkforward import CATEGORIES,prediction

DIVISIONS={"Atlantic":"BOS BUF DET FLA MTL OTT TBL TOR","Metropolitan":"CAR CBJ NJD NYI NYR PHI PIT WSH","Central":"CHI COL DAL MIN NSH STL UTA WPG","Pacific":"ANA CGY EDM LAK SEA SJS VAN VGK"}
DIV={x:division for division,teams in DIVISIONS.items() for x in teams.split()}
RIVALS={frozenset(p.split("-")) for p in ("BOS-MTL","BOS-TOR","EDM-CGY","PIT-PHI","PIT-WSH","NYR-NYI","NYR-NJD","TOR-OTT","LAK-ANA","VGK-SJS","FLA-TBL")}

def unit_evidence(history,baseline,expected,as_of):
 r=compare(history,baseline,expected,as_of)
 by_unit={}
 for unit in ("top6","middle6","bottom6","top4_d","depth_d"):
  def extract(key):
   observed=[p for p in r[key]["players"].values() if p["unit"]==unit]
   wanted=sum(x["expected_share"] for x in (baseline if key=="baseline" else expected)["players"]
     if x["unit"]==unit and x["status"]!="out")
   observed_weight=sum(p["share"] for p in observed)
   value=sum(p["contribution"] for p in observed)
   return {"coverage":round(observed_weight/wanted,6) if wanted else None,
     "offense_proxy":round(value,6) if wanted and abs(observed_weight-wanted)<1e-9 else None,
     "requested_weight":round(wanted,6)}
  b,e=extract("baseline"),extract("expected")
  by_unit[unit]={"baseline":b,"expected":e,
   "delta_offense_proxy":round(e["offense_proxy"]-b["offense_proxy"],6)
   if b["offense_proxy"] is not None and e["offense_proxy"] is not None else None}
 return {"units":by_unit,"availability":r,"full_crs":None,"defense_rating":None,
    "units_validated":False}

def context(fixture,observations,as_of):
 if timepoint(fixture["start"])<=timepoint(as_of):raise ValueError("Pregame cutoff violated")
 h,a=fixture["home"],fixture["away"]
 if h==a:raise ValueError("Same teams")
 if fixture.get("venue_confirmed") is not True:home_ice=None
 else:home_ice=h
 prior=[r for r in observations if timepoint(r["as_of"])<=timepoint(as_of)]
 if len(prior)!=len(observations):raise ValueError("Future context observations")
 def latest(kind,team):
  rows=[r for r in prior if r["kind"]==kind and r["team"]==team and r.get("source")]
  return max(rows,key=lambda r:timepoint(r["as_of"])) if rows else None
 def special(team):
  pp,pk=latest("pp",team),latest("pk",team)
  def shrink(row):
   if not row:return None
   n=row.get("chances");made=row.get("conversions")
   if not isinstance(n,int) or not isinstance(made,int) or n<1 or not 0<=made<=n:raise ValueError("Invalid ST counts")
   return {"opportunities":n,"conversions":made,"raw":round(made/n,6),
    "beta_shrunk":round((made+2)/(n+10),6),"as_of":row["as_of"],"source":row["source"]}
  return {"pp":shrink(pp),"pk_opponent_conversions_allowed":shrink(pk),
    "sustainable_strength_validated":False}
 rest={}
 for team in (h,a):
  x=latest("rest",team)
  if x and (not isinstance(x.get("days"),int) or x["days"]<0):raise ValueError("Invalid rest")
  rest[team]=x["days"] if x else None
 return {"home":h,"away":a,"home_ice":home_ice,"rest_days":rest,
  "division":DIV.get(h) is not None and DIV[h]==DIV.get(a),
  "rivalry":frozenset((h,a)) in RIVALS,"rivalry_tier":"A" if frozenset((h,a)) in RIVALS else None,
  "special_teams":{h:special(h),a:special(a)},
  "travel_distance":None,"referees":None,"tactical_familiarity":None,
  "context_probabilistic_effect_validated":False}

def baseline_probabilities(global_counts,team_counts,home,away):
 from collections import defaultdict
 # Counts are explicitly previous-date aggregates supplied by the caller.
 result={}
 for target,cats in CATEGORIES.items():
  glob=global_counts.get(target,{})
  hc=team_counts.get("home:"+home,{}).get(target,{})
  ac=team_counts.get("away:"+away,{}).get(target,{})
  prior=[glob.get(c,0)+1 for c in cats]
  s=sum(prior);prior=[x/s for x in prior]
  counts=[hc.get(c,0)+ac.get(c,0) for c in cats]
  total=sum(counts)
  vals=[(counts[i]+80*prior[i])/(total+80) for i in range(len(cats))]
  result[target]={c:round(vals[i],6) for i,c in enumerate(cats)}
 return result

def assemble(spec):
 as_of=spec["as_of"];fixture=spec["fixture"]
 if not (timepoint(spec["history"]["date"]+"T00:00:00+00:00")<timepoint(as_of)):
  raise ValueError("History must precede as-of instant")
 if spec["history"]["team"]!=fixture["home"]:raise ValueError("Home history team mismatch")
 crs=unit_evidence(spec["history"],spec["baseline_lineup"],spec["expected_lineup"],as_of)
 ctx=context(fixture,spec.get("observations",[]),as_of)
 counts=spec.get("historical_counts")
 if not counts or counts.get("cutoff_date","9999")>=as_of[:10] or not counts.get("source"):
  raise ValueError("Require dated, independently sourced previous-date outcome counts")
 probs=baseline_probabilities(counts["global"],counts["teams"],fixture["home"],fixture["away"])
 return {"fixture":fixture,"as_of":as_of,"crs_research":crs,"context_research":ctx,
   "two_sided_probabilities_research":probs,
   "first_to_plus3":probs["first3"],"3glp":{"home":probs["home3"],"away":probs["away3"]},
   "duals_not_calibrated":True,"baseline_only_no_context_or_crs_fitting":True,
   "official_model_outputs":None,"challenger_2026_27_1_outputs":None,
   "probabilities_validated":False,"full_14_modules_executed":False,
   "missing_modules":["confirmed_full_lineups","defensive_crs","actual_goalie_daily_rating",
      "special_teams_quality_adjustment","travel","referees","calibrated_crs_context_effects"],
   "odds_used":False,"promoted":False}

def main():
 p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--output",required=True)
 a=p.parse_args();result=assemble(json.loads(Path(a.input).read_text()))
 dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2))
 print(json.dumps({"game":result["fixture"].get("game_id"),"official_promoted":False,
  "all_modules_complete":False,"research_target_count":len(result["two_sided_probabilities_research"])},indent=2))
if __name__=="__main__":main()
