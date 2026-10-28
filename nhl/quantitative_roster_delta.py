"""Quantitative *skater evidence* CRS and availability delta, not full NHL CRS.

Both baseline and expected lineup require independent dated source metadata.
Use exactly the same prior-date player histories and the same normalization.
Skater production is an observational proxy, NOT causal value, xG or wins.
Goalie/defense quality are unscored until identity-level evidence exists.
"""
import argparse,json,math
from pathlib import Path
try:
    from nhl.roster_aware_units import validate,timepoint,UNITS
except ModuleNotFoundError:
    from roster_aware_units import validate,timepoint,UNITS

SKATER_UNITS=tuple(u for u in UNITS if u!="goalie")
def scorer(history,roster,prediction_time,minimum_games=3):
    players=validate(roster,prediction_time,history["team"])
    details={};missing=[];numerator=denominator=0.
    for row in players:
        if row["status"]=="out" or row["expected_share"]==0:continue
        unit=row["unit"];pid=str(row["player_id"])
        if unit=="goalie":continue
        past=history.get("players",{}).get(pid)
        if not past or past.get("role")!="skater" or past.get("observed",0)<minimum_games:
            missing.append(int(pid));continue
        n=past["observed"];share=row["expected_share"]
        goals=past["goals"]/n;shots=past["shots"]/n
        if goals<0 or shots<goals:raise ValueError("Invalid historic player metrics")
        # Stable explicit index in average observed shots and goals per player-game.
        value=goals+0.05*shots
        numerator+=share*value;denominator+=share
        details[pid]={"unit":unit,"share":share,"historic_goals_per_game":round(goals,6),
          "historic_shots_per_game":round(shots,6),"contribution":round(share*value,6),
          "observed_games":n}
    requested=sum(x["expected_share"] for x in players if x["unit"]!="goalie" and x["status"]!="out")
    coverage=denominator/requested if requested else None
    complete=bool(requested) and abs(denominator-requested)<1e-9
    return {"value":round(numerator,6) if complete else None,
      "partial_observed_sum":round(numerator,6),"coverage":round(coverage,6) if coverage is not None else None,
      "missing":missing,"players":details,"observed_weight":round(denominator,6),
      "requested_weight":round(requested,6),"complete":complete}

def compare(history,baseline,expected,prediction_time,minimum_games=3):
    if timepoint(prediction_time).date().isoformat()<history.get("date","0000-01-01"):
        raise ValueError("History date later than prediction date")
    if minimum_games<1:raise ValueError("Invalid minimum sample")
    b=scorer(history,baseline,prediction_time,minimum_games)
    e=scorer(history,expected,prediction_time,minimum_games)
    # Explicitly only skater offensive evidence, with no unsupported goalie score.
    valid=b["complete"] and e["complete"]
    delta=round(e["value"]-b["value"],6) if valid else None
    b_ids={p["player_id"] for p in baseline["players"] if p["status"]!="out" and p["expected_share"]>0}
    e_ids={p["player_id"] for p in expected["players"] if p["status"]!="out" and p["expected_share"]>0}
    return {"team":history["team"],"baseline_source":baseline["source"],"expected_source":expected["source"],
      "baseline_as_of":baseline["as_of"],"expected_as_of":expected["as_of"],
      "prediction_time":prediction_time,
      "crs_skater_offense_proxy":e["value"],"baseline_skater_offense_proxy":b["value"],
      "availability_delta_skater_offense_proxy":delta,
      "outgoing_ids":sorted(b_ids-e_ids),"incoming_ids":sorted(e_ids-b_ids),
      "baseline":b,"expected":e,"goalie_rating":None,"defensive_crs":None,
      "full_crs_numeric_rating":None,"full_availability_delta":None,
      "interpretation":"Quantitative observed skater offense proxy (weighted goals/game + 0.05 shots/game). NOT full team CRS, NHL goals, player causal impact, win probability, or validated prediction.",
      "odds_used":False,"official_model_promoted":False}

def main():
    p=argparse.ArgumentParser()
    for n in ("history","game-id","side","baseline","expected","prediction-time","output"):
        p.add_argument("--"+n,required=True)
    a=p.parse_args();hist=json.loads(Path(a.history).read_text())
    matches=[r for r in hist if r["game_id"]==a.game_id]
    if len(matches)!=1 or a.side not in ("home","away"):raise ValueError("Invalid game identity")
    h=dict(matches[0][a.side],date=matches[0]["date"])
    result=compare(h,json.loads(Path(a.baseline).read_text()),json.loads(Path(a.expected).read_text()),a.prediction_time)
    dst=Path(a.output);dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(json.dumps(result,indent=2))
    print(json.dumps({"team":result["team"],"crs_skater_offense_proxy":result["crs_skater_offense_proxy"],
                      "availability_delta_skater_offense_proxy":result["availability_delta_skater_offense_proxy"],
                      "full_crs_numeric_rating":None},indent=2))
if __name__=="__main__":main()
