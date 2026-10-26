"""Shared, fail-closed pregame result contract across NBA, NFL, NHL, tennis and soccer.

A sporting model remains sport-specific. Shared validation cannot manufacture
predictions, verify data providers or independently calibrate a challenger.
"""
import math
from datetime import datetime, timezone

SPORTS=("nba","nfl","nhl","tennis","soccer")

def utc(value):
    date=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if date.tzinfo is None or date.utcoffset()!=timezone.utc.utcoffset(date):
        raise ValueError("UTC timestamp required")
    return date

def probability(value):
    return type(value) in (int,float) and math.isfinite(value) and 0<value<1

def validate_report(report):
    sport=report.get("sport")
    if sport not in SPORTS:raise ValueError("Unsupported sport")
    as_of=utc(report["as_of_utc"])
    if report.get("odds_used_in_sport_model") is not False:
        raise ValueError("Sporting forecasts cannot use market odds")
    games=report.get("events")
    if not isinstance(games,list):raise ValueError("Events must be a list")
    seen=set()
    for game in games:
        gid=str(game.get("event_id",""))
        if not gid or gid in seen:raise ValueError("Missing or duplicate event ID")
        seen.add(gid)
        tip=utc(game["start_utc"])
        if as_of>=tip:raise ValueError("Event already started; not pregame")
        sides=game.get("participants")
        if not isinstance(sides,list) or len(sides)!=2 or not all(isinstance(x,str) and x.strip() for x in sides) or sides[0]==sides[1]:
            raise ValueError("Exactly two different participants required")
        base=game.get("official_baseline")
        challenger=game.get("challenger")
        for candidate in (base,challenger):
            if candidate is not None and not probability(candidate):
                raise ValueError("Invalid baseline/challenger probability")
        outcome=game.get("final_probability")
        if outcome is not None:
            if not probability(outcome):raise ValueError("Invalid final probability")
            if (game.get("all_inputs_verified") is not True or
                game.get("independent_validation_passed") is not True or
                not game.get("validation_report_ref")):
                raise ValueError("Unvalidated integrated probability")
        if sport=="soccer":
            draw=game.get("draw_probability")
            if draw is not None and not probability(draw):raise ValueError("Invalid draw probability")
            if outcome is not None and draw is None:
                raise ValueError("Soccer final requires three-way outcomes")
            if outcome is not None and game.get("away_probability") is None:
                raise ValueError("Soccer away probability missing")
            if outcome is not None and (not probability(game["away_probability"]) or
                abs(outcome+draw+game["away_probability"]-1)>1e-6):
                raise ValueError("Soccer three-way probabilities must sum to one")
        elif game.get("draw_probability") is not None:
            raise ValueError("No three-way draw probability in two-way forecast")
        if sport!="soccer" and outcome is not None:
            away=game.get("away_probability")
            if not probability(away) or abs(outcome+away-1)>1e-6:
                raise ValueError("Two-way probabilities must sum to one")
    return {"sport":sport,"events_verified_for_structure":len(games),
            "verified_probabilities":sum(g.get("final_probability") is not None for g in games),
            "complete_vs_input":True,"complete_vs_league":False,
            "note":"Structural checks only; schedule coverage and statistical validation remain separate."}
