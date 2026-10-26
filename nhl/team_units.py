"""NHL point-in-time team units: explicit data availability, never inferred from standings.

Inputs are verified observations, not calibrated probability impacts. Require
timestamps/sources for roster units, goalie, and PP/PK independently.
"""
import math
from datetime import datetime,timezone

UNITS=("forwards","defense","supporting_cast","goalie","power_play","penalty_kill")
def utc(x):
    d=datetime.fromisoformat(str(x).replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("Timezone required")
    return d.astimezone(timezone.utc)

def team_units(payload,as_of,tipoff,team):
    freeze=utc(as_of);tip=utc(tipoff)
    if freeze>=tip:raise ValueError("Only future games")
    if payload.get("team")!=team:raise ValueError("Wrong team")
    result={};missing=[]
    for unit in UNITS:
        x=payload.get(unit)
        if not isinstance(x,dict):
            missing.append(unit);continue
        try:timely=utc(x["observed_at_utc"])<=freeze and utc(x["observed_at_utc"])<tip
        except (KeyError,ValueError,TypeError):timely=False
        value=x.get("rating")
        if not (timely and isinstance(x.get("source_url"),str) and
                x["source_url"].startswith("https://") and
                x.get("source_verified") is True and
                type(value) in (float,int) and math.isfinite(value) and 0<=value<=100):
            missing.append(unit);continue
        result[unit]={"rating":value,"source_url":x["source_url"],
                      "observed_at_utc":x["observed_at_utc"]}
    full=not missing
    # A scalar CRS is intentionally not synthesized from arbitrary units:
    # calibration must learn contribution weights on historical holdouts.
    return {"team":team,"units":result,"missing":missing,"full_evidence":full,
            "crs":None,"goalie_win_impact":None,"special_teams_win_impact":None,
            "calibrated":False}

def game_units(home,away,as_of,tipoff,home_team,away_team):
    h=team_units(home,as_of,tipoff,home_team)
    a=team_units(away,as_of,tipoff,away_team)
    return {"home":h,"away":a,
            "market_estimates":{"ml":None,"regulation_draw":None,
             "home_3glp":None,"away_3glp":None,
             "first_to_plus_three_home":None,"first_to_plus_three_away":None},
            "independent_market_calibration":False,
            "roster_weighting_validated":False}
