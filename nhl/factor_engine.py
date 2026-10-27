"""NHL exploratory factor engine. All weights are explicit hypotheses, NOT fitted.

Uses only documented current-season observations. Unknown starters, verified
units, matchup injuries and PP opportunities produce no invented adjustment.
"""
import math
from module_audit import context

def bounded(x,lo,hi):
    return max(lo,min(hi,x))

def valid(x):
    return type(x) in (float,int) and math.isfinite(x)

def shrink(value,games,center=3.0,prior=5):
    if not valid(value) or not valid(games) or games<=0 or value<0:
        raise ValueError("Invalid season rate")
    return (games*value+prior*center)/(games+prior)

def strength(side,opponent):
    a=side["crs_evidence"];b=opponent["crs_evidence"]
    gp=a["games_played"];gpo=b["games_played"]
    gf=shrink(a["goals_for_per_game"],gp)
    ga=shrink(b["goals_against_per_game"],gpo)
    return 0.5*(gf+ga)

def pp_pct(side):
    x=side["special_teams_evidence"].get("power_play_pct_observed")
    return x if valid(x) and 0<=x<=1 else None

def pk_pct(side):
    x=side["special_teams_evidence"].get("penalty_kill_pct_observed")
    return x if valid(x) and 0<=x<=1 else None

def process(game):
    home=game["home_evidence"];away=game["away_evidence"]
    hbase=strength(home,away);abase=strength(away,home)
    # Raw season PP/PK percentages describe previous play. Without counts,
    # opponent strength and fitted regression, use them as annotations only.
    hpp=pp_pct(home);app=pp_pct(away)
    hpk=pk_pct(home);apk=pk_pct(away)
    # Shots proxy adds limited explanatory variation; avoid double-counting goals.
    # Per-game shot totals may be unavailable -> zero adjustment.
    def shooting_side(a,b):
        x=a["crs_evidence"].get("shots_for_per_game")
        y=b["crs_evidence"].get("shots_against_per_game")
        if not valid(x) or not valid(y) or x<0 or y<0:
            return 0.0,False
        return bounded(((x+y)/2-30)/30,-0.20,0.20)*0.12,True
    hs,hsok=shooting_side(home,away);a_s,asok=shooting_side(away,home)
    # No speculative lineup/goalie assignment. Their observed season totals
    # are included in provenance but not injected into scoring rates.
    lh=bounded(hbase*(1+hs),0.5,7.0)
    la=bounded(abase*(1+a_s),0.5,7.0)
    ctx=context(game["home_team"],game["away_team"])
    return {"home_goals_rate":lh,"away_goals_rate":la,
            "factor_audit":{"home_scoring_base":round(hbase,4),
              "away_scoring_base":round(abase,4),
              "shot_proxy_home_multiplier":round(1+hs,5),
              "shot_proxy_away_multiplier":round(1+a_s,5),
              "shots_measured_home":hsok,"shots_measured_away":asok,
              "pp_observed_home":hpp,"pp_observed_away":app,
              "pk_observed_home":hpk,"pk_observed_away":apk,
              "pp_pk_applied":False,"reason_pp_pk":"no verified opportunities or fitted coefficient",
              "goalie_applied":False,"reason_goalie":"starting goalies not confirmed",
              "unit_applied":False,"reason_units":"deployment not confirmed",
              "crs_rating_applied":False,"reason_crs":"no trained roster valuation",
              "division":ctx["divisional"],"rivalry_tier":ctx["rivalry_tier"],
              "division_probability_adjustment_applied":False,
              "home_ice_probability_adjustment_applied":False,
              "factor_weights_fitted":False,
              "exploratory":True}}
