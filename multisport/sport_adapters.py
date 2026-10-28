"""Read-only adapters to common five-sport evidence/report format.

No claim of certified official forecasts: raw pipeline forecasts remain
research candidates until source lineage and independent validation exist.
"""
import argparse,json
from pathlib import Path
from datetime import datetime,timezone
from multisport.model_registry import SPORTS
from multisport.contract import validate_report

def utc(value):
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("Missing timezone")
    return d.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def adapt(sport,source,revision="unrecorded"):
    if sport not in ("nba","nfl","nhl"):raise ValueError("Only implemented sport adapters")
    stamp=source.get("as_of_utc") or source.get("created_at_utc")
    if not stamp:raise ValueError("Missing evidence timestamp")
    stamp=utc(stamp)
    games=source.get("events") if sport=="nfl" else source.get("games") if sport=="nhl" else source.get("predictions")
    if not isinstance(games,list):raise ValueError("Missing source event list")
    events=[]
    for x in games:
        gid=x.get("event_id") or x.get("game_id")
        start=x.get("start_utc") or x.get("tipoff_utc") or x.get("start_time_utc")
        home=x.get("home_team") or x.get("home")
        away=x.get("away_team") or x.get("away")
        if not (gid and start and home and away):raise ValueError("Incomplete match identity and start")
        # Keep uncertified candidate numbers in source only, never republish
        # them as validated official baseline/challenger predictions.
        events.append({"event_id":str(gid),"start_utc":utc(start),
                       "participants":[str(home),str(away)],
                       "official_baseline":None,"challenger":None,
                       "final_probability":None,
                       "source_candidate_available":any(k in x for k in (
                          "statistical_p_home","illustrative_ml","p_home",
                          "p_home_elo","baseline_p_home","p_challenger"))})
    report={"sport":sport,"as_of_utc":stamp,"odds_used_in_sport_model":False,
            "events":events,"source_revision":revision,
            "verified_point_in_time_source":False,
            "source_input_declares_no_odds":source.get("odds_used") is False or source.get("odds_used_in_sport_model") is False,
            "automatic_promotion":False}
    # The no-odds field is a publication policy, not an audit that the original
    # source really omitted prices. The original source must be audited.
    validate_report(report)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sport",required=True,choices=("nba","nfl","nhl"))
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    p.add_argument("--revision",default="unrecorded")
    a=p.parse_args()
    result=adapt(a.sport,json.loads(Path(a.input).read_text()),a.revision)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2))
    print(json.dumps({"sport":a.sport,"events":len(result["events"]),
                      "validated_predictions":0,"auto_promoted":False}))
if __name__=="__main__":main()
