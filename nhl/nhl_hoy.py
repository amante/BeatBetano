"""NHL hoy exploratory sports-only baseline from prior-day official NHL standings.

Not a calibrated CRS/goalie/3GLP model. Never use same-day standings which can
contain results unavailable at freeze time. Missing data produces no probabilities.
"""
import argparse,json,math
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import requests
API="https://api-web.nhle.com/v1"

def moment(value):
    d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("Timezone required")
    return d.astimezone(timezone.utc)

def slate(score,standings,as_of,game_date):
    now=moment(as_of)
    if not isinstance(score.get("games"),list) or not isinstance(standings.get("standings"),list):
        raise ValueError("Official NHL score/standings required")
    day=date.fromisoformat(game_date)
    if day>now.date()+timedelta(days=2) or day<now.date():
        raise ValueError("Use current or near-future NHL slate only; prior-day snapshot cannot backtest retrospectively")
    base={}
    for r in standings["standings"]:
        abbr=r.get("teamAbbrev",{})
        abbr=abbr.get("default") if isinstance(abbr,dict) else abbr
        if abbr:
            gp=r.get("gamesPlayed");goals=r.get("goalDifferential")
            if type(gp) is int and gp>=0 and type(goals) in (int,float) and math.isfinite(goals):
                base[abbr]={"games":gp,"goal_diff":goals}
    events=[];seen=set();skipped=[]
    for g in score["games"]:
        if g.get("gameType")!=2:continue
        eid=str(g.get("id",""))
        home=g.get("homeTeam",{}).get("abbrev");away=g.get("awayTeam",{}).get("abbrev")
        tip=moment(g["startTimeUTC"])
        if not eid or eid in seen:raise ValueError("Duplicate/missing NHL event ID")
        seen.add(eid)
        if g.get("gameState") not in ("FUT","PRE") or tip<=now:
            skipped.append(eid);continue
        if home not in base or away not in base:
            p=None;reason="missing_historical_team_standings"
        else:
            # Purely exploratory, deliberately shrunk goal differential per game.
            # Not a fitted or backtested win model.
            def quality(t):
                row=base[t];return row["goal_diff"]/(row["games"]+10)
            diff=max(-3,min(3,quality(home)-quality(away)))
            p=round(1/(1+math.exp(-(0.16+0.35*diff))),6)
            reason="exploratory_statistical_only"
        events.append({"event_id":eid,"home_team":home,"away_team":away,
            "start_utc":tip.isoformat(),"statistical_p_home":p,
            "statistical_p_away":round(1-p,6) if p is not None else None,
            "official_baseline":None,"challenger":None,"final_probability":None,
            "regulation_win_home":None,"regulation_draw":None,"regulation_win_away":None,
            "three_goal_lead_home":None,"three_goal_lead_away":None,
            "first_to_plus_three_home":None,"first_to_plus_three_away":None,
            "goalie_confirmed":False,"special_teams_verified":False,
            "roster_verified":False,"rivalry_verified":False,
            "eligible_for_bet":False,"status":reason})
    return {"schema_version":1,"sport":"nhl","as_of_utc":now.isoformat(),
        "date":game_date,"source_score":API+"/score/"+game_date,
        "source_standings":API+"/standings/"+(day-timedelta(days=1)).isoformat(),
        "standings_effective_prior_day":True,"odds_used_in_sport_model":False,
        "events":events,"started_or_finished":skipped,
        "fixture_coverage_vs_source":True,"fixture_coverage_vs_league_verified":False,
        "note":"Not official calibrated model; goalie, RT draw, 3GLP and rivalry modules are not yet computed."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();day=date.fromisoformat(a.date)
    as_of=datetime.now(timezone.utc).isoformat()
    result=[]
    for suffix in ("/score/"+a.date,"/standings/"+(day-timedelta(days=1)).isoformat()):
        response=requests.get(API+suffix,timeout=35);response.raise_for_status()
        result.append(response.json())
    report=slate(result[0],result[1],as_of,a.date)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2))
    print(json.dumps({"pregame":len(report["events"]),"estimates":sum(g["statistical_p_home"] is not None for g in report["events"])}))
if __name__=="__main__":main()
