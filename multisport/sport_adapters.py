"""Read-only adapters to common five-sport evidence/report format.

No claim of certified official forecasts: raw pipeline forecasts remain
research candidates until source lineage and independent validation exist.
"""
import argparse,json
from pathlib import Path
from datetime import datetime,timezone
from multisport.model_registry import SPORTS
from multisport.contract import validate_report
from multisport.forecast_revisions import make_forecast, snapshot, save_snapshot

def utc(value):
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("Missing timezone")
    return d.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def source_probabilities(sport, event):
    values=event.get('forecast_probabilities')
    if values is not None:
        return values,'forecast_probabilities'
    if sport=='soccer':
        values=event.get('probabilities')
        if isinstance(values,list) and len(values)==3:
            return dict(zip(('home','draw','away'),values)),'probabilities'
        if isinstance(values,dict):return values,'probabilities'
        return None,None
    for key in ('elo_p_home','historical_elo_candidate','statistical_p_home','p_home','p_home_elo','baseline_p_home','p_challenger'):
        if event.get(key) is not None:
            p=event[key]
            if type(p) not in (int,float):raise ValueError('Invalid source forecast probability')
            return {'home':p,'away':1-p},key
    illustrative=event.get('illustrative_ml')
    if isinstance(illustrative,dict) and illustrative.get('home') is not None:
        p=illustrative['home']
        if type(p) not in (int,float):raise ValueError('Invalid source forecast probability')
        return {'home':p,'away':illustrative.get('away',1-p)},'illustrative_ml'
    return None,None


def adapt(sport,source,revision="unrecorded",stage="initial"):
    if sport not in SPORTS:raise ValueError("Unsupported sport")
    if source.get('odds_used') is True or source.get('odds_used_in_sport_model') is True:
        raise ValueError('Market odds prohibited')
    stamp=source.get("as_of_utc") or source.get("created_at_utc")
    if not stamp:raise ValueError("Missing evidence timestamp")
    stamp=utc(stamp)
    games=source.get("predictions") if sport=="nba" else source.get("games",source.get("events")) if sport=="nhl" else source.get("events")
    if not isinstance(games,list):raise ValueError("Missing source event list")
    events=[]
    for x in games:
        gid=x.get("event_id") or x.get("game_id")
        start=x.get("start_utc") or x.get("tipoff_utc") or x.get("start_time_utc")
        home=x.get("home_team") or x.get("home")
        away=x.get("away_team") or x.get("away")
        if not (gid and start and home and away):raise ValueError("Incomplete match identity and start")
        for key in ('observed_at_utc','feature_as_of_utc','prediction_as_of_utc'):
            if x.get(key) is not None and datetime.fromisoformat(utc(x[key]).replace('Z','+00:00'))>datetime.fromisoformat(stamp.replace('Z','+00:00')):
                raise ValueError('Source observation follows forecast cutoff')
        values,source_key=source_probabilities(sport,x)
        forecast=None
        if values is not None:
            forecast=make_forecast(sport,values,str(x.get('model_version') or source.get('model_version') or revision),stage,
                assumptions=x.get('assumptions',['Existing source-model forecast; availability has not been independently audited by this adapter.']),
                unresolved_inputs=x.get('unresolved_inputs',['Current lineup and availability not verified by this adapter']))
            forecast['source_probability_field']=source_key
            forecast['source_classification']='illustrative' if source_key=='illustrative_ml' else 'unvalidated_model_output'
        # Publish source probabilities separately from certified production output.
        events.append({"event_id":str(gid),"start_utc":utc(start),
                       "participants":[str(home),str(away)],
                       "official_baseline":None,"challenger":None,
                       "final_probability":None,"forecast":forecast,
                       "forecast_unavailable_reason":None if forecast else "No source-model probability available",
                       "source_candidate_available":forecast is not None})
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
    p.add_argument("--sport",required=True,choices=SPORTS)
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    p.add_argument("--revision",default="unrecorded")
    p.add_argument("--stage",choices=("initial","update","final_pregame"),default="initial")
    p.add_argument("--previous-snapshot")
    a=p.parse_args()
    result=adapt(a.sport,json.loads(Path(a.input).read_text()),a.revision,a.stage)
    previous=json.loads(Path(a.previous_snapshot).read_text()) if a.previous_snapshot else None
    result=snapshot(result,previous)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    save_snapshot(path,result)
    print(json.dumps({"sport":a.sport,"events":len(result["events"]),
                      "validated_predictions":0,"auto_promoted":False}))
if __name__=="__main__":main()
