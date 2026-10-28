"""Conservative pregame roster evidence adapter.

This does not fetch or manufacture live lineups. An explicitly supplied
time-stamped, sourced lineup can be normalized against earlier-date histories.
Unknown goalie performance, defensive quality and TOI remain unknown.
"""
import argparse,json
from pathlib import Path
try:
    from nhl.quantitative_roster_delta import compare
    from nhl.roster_aware_units import timepoint
except ModuleNotFoundError:
    from quantitative_roster_delta import compare
    from roster_aware_units import timepoint

def adapt(snapshot,team,prediction_time):
    if snapshot.get("team")!=team:raise ValueError("Team mismatch")
    if not snapshot.get("source_url") or not snapshot.get("as_of"):
        raise ValueError("Source URL and as-of required")
    if not str(snapshot["source_url"]).startswith("https://"):raise ValueError("HTTPS source URL required")
    if timepoint(snapshot["as_of"])>timepoint(prediction_time):raise ValueError("Lineup newer than prediction")
    if snapshot.get("lineup_type") not in ("projected","confirmed"):
        raise ValueError("Unknown lineup type")
    players=[];seen=set()
    for p in snapshot.get("players",[]):
        pid=p.get("player_id");unit=p.get("unit");status=p.get("status")
        if not isinstance(pid,int) or pid<=0 or pid in seen:raise ValueError("Invalid/duplicate player ID")
        seen.add(pid)
        if status not in ("confirmed","projected","out"):raise ValueError("Unknown player availability")
        if snapshot["lineup_type"]=="projected" and status=="confirmed":
            raise ValueError("Projected lineup cannot assert confirmed players")
        players.append({"player_id":pid,"unit":unit,"status":status,
                        "expected_share":p.get("expected_share")})
    if not players:raise ValueError("Empty source lineup")
    return {"team":team,"source":snapshot["source_url"],"as_of":snapshot["as_of"],"players":players}

def evaluate(history,baseline_source,expected_source,prediction_time):
    team=history["team"]
    baseline=adapt(baseline_source,team,prediction_time)
    expected=adapt(expected_source,team,prediction_time)
    result=compare(history,baseline,expected,prediction_time)
    result["source_contract"]="Provided evidence only; HTTP fetching and source truth verification not implemented"
    result["unavailable_metrics"]=["individual_goalie_save_pct","skater_TOI","defensive_xG","pair_on_ice_impact"]
    return result

def main():
    p=argparse.ArgumentParser()
    for arg in ("history","game-id","side","baseline-source","expected-source","prediction-time","output"):
        p.add_argument("--"+arg,required=True)
    a=p.parse_args()
    history=json.loads(Path(a.history).read_text())
    matched=[r for r in history if r["game_id"]==a.game_id]
    if len(matched)!=1 or a.side not in ("home","away"):raise ValueError("Missing fixture side")
    past=dict(matched[0][a.side],date=matched[0]["date"])
    result=evaluate(past,json.loads(Path(a.baseline_source).read_text()),
                    json.loads(Path(a.expected_source).read_text()),a.prediction_time)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2))
    print(json.dumps({"team":result["team"],"skater_crs_proxy":result["crs_skater_offense_proxy"],
                      "availability_delta":result["availability_delta_skater_offense_proxy"],
                      "unavailable_metrics":result["unavailable_metrics"]},indent=2))
if __name__=="__main__":main()
