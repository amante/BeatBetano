"""Observed four-pillar NHL feature sheet, strictly point-in-time.

No bookmaker inputs, calibrated probabilities, invented lineup assignments or
unit/roster ratings. Descriptive measures must never be promoted into CRS.
"""
import argparse
import json
import math
from pathlib import Path

def finite(x):
    return type(x) in (int, float) and math.isfinite(x)

def rate(x):
    return round(float(x), 4) if finite(x) and 0 <= x <= 100 else None

def team_form(row):
    if not isinstance(row, dict):
        return {"status": "missing", "goal_differential_per_game": None,
                "games_played": None, "crs": None}
    gp = row.get("gamesPlayed")
    gd = row.get("goalDifferential")
    enough = type(gp) is int and gp > 0 and finite(gd)
    return {"status": "observed_only" if enough else "missing",
            "games_played": gp if type(gp) is int and gp >= 0 else None,
            "goal_differential_per_game": round(gd/gp, 4) if enough else None,
            "goals_for_per_game": row.get("goals_for_per_game"),
            "goals_against_per_game": row.get("goals_against_per_game"),
            "roster_verified": False, "crs": None,
            "reason": "team_form_is_not_current_roster_strength"}

def teams_special(row):
    if not isinstance(row, dict):
        row = {}
    pp, pk = rate(row.get("power_play_pct_observed")), rate(row.get("penalty_kill_pct_observed"))
    return {"status": "observed_only" if pp is not None and pk is not None else "missing",
            "pp_percent": pp, "pk_percent": pk,
            "power_play_opportunities": None, "penalty_kill_opportunities": None,
            "bayesian_pp_strength": None, "bayesian_pk_strength": None,
            "reason": "standings_percentages_lack_attempt_counts_for_beta_binomial_update"}

def goalie_rows(obs, side):
    payload = obs.get(side, {}) if isinstance(obs, dict) else {}
    rows = []
    for r in payload.get("goalie_candidates", []):
        n = r.get("shots_against")
        saved = r.get("saves")
        if type(n) is not int or type(saved) is not int or not 0 <= saved <= n:
            continue
        p = saved/n if n else None
        # Wilson 95% interval, descriptive sampling uncertainty only.
        z=1.96
        if p is None:
            interval = None
        else:
            mid = (p + z*z/(2*n))/(1+z*z/n)
            half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
            interval = [round(max(0,mid-half),4),round(min(1,mid+half),4)]
        rows.append({"goalie_id":r.get("goalie_id"),
                     "save_percentage":round(p,4) if p is not None else None,
                     "shots_against":n,"sample_games":r.get("sample_games"),
                     "starts_last_7_days":r.get("starts_last_7_days"),
                     "sv_95pct_wilson_interval": interval,
                     "starting_goalie_confirmed":False,"goalie_daily_rating":None,
                     "gsax":r.get("gsax"),"source_url":r.get("source_url")})
    return {"status": "observed_only" if rows else "missing",
            "candidates": rows, "starter_confirmed":False,
            "goalie_daily_rating":None,"reason":"roster_candidates_not_confirmed_starters"}

def build(slate, goalie):
    if slate.get("sport")!="nhl" or goalie.get("sport")!="nhl" or slate.get("as_of_utc")!=goalie.get("as_of_utc"):
        raise ValueError("NHL point-in-time inputs required")
    games=[]
    for event in slate.get("events",[]):
        gid=str(event["event_id"])
        obs=goalie.get("games",{}).get(gid,{})
        stats=event.get("official_team_stats") or {}
        sides={}
        for side in ("home","away"):
            row=stats.get(side)
            sides[side]={"team":event[side+"_team"],
                         "team_form":team_form(row),
                         "unit_ratings":{"status":"missing", "forward_top6":None,
                                         "forward_middle6":None,"forward_bottom6":None,
                                         "defense_top4":None,"supporting_cast":None,
                                         "reason":"no_verified_point_in_time_line_combinations"},
                         "goalie":goalie_rows(obs,side),
                         "special_teams":teams_special(row)}
        games.append({"event_id":gid,"home":sides["home"],"away":sides["away"],
                      "crs_delta":None,"unit_delta":None,"goalie_delta":None,
                      "pp_pk_delta":None,"eligible_for_bet":False})
    return {"sport":"nhl","as_of_utc":slate["as_of_utc"],
            "games":games,"calibrated":False,"odds_used":False,
            "note":"Official team form, PP/PK, candidate goalie SV and uncertainty, never CRS or fitted ratings."}

def summary(report):
    out=["## NHL — Four-pillar observed evidence (not calibrated)",
         "CRS and Unit Ratings require verified lineups; goalie candidates are not starters; PP/PK percentages are not sustainable estimates.","",
         "| Game | Team | GP | GD/GP | PP% | PK% | Goalies measured | CRS | Units |",
         "|---|---|---:|---:|---:|---:|---:|---|---|"]
    for g in report["games"]:
        for side in ("away","home"):
            r=g[side]; f=r["team_form"];p=r["special_teams"]
            fmt=lambda x: "—" if x is None else str(x)
            out.append("| "+ " | ".join([g["event_id"],r["team"],fmt(f["games_played"]),fmt(f["goal_differential_per_game"]),fmt(p["pp_percent"]),fmt(p["pk_percent"]),str(len(r["goalie"]["candidates"])),"unavailable","unavailable"])+" |")
    out.extend(["","**Gate:** descriptive evidence only; no official ML, RT, +3, DUAL or FUERTE predictions."])
    return "\n".join(out)+"\n"

def main():
    p=argparse.ArgumentParser()
    for name in ("slate","goalies","output","summary"):
        p.add_argument("--"+name,required=True)
    args=p.parse_args()
    result=build(json.loads(Path(args.slate).read_text()),
                 json.loads(Path(args.goalies).read_text()))
    for filename,content in ((args.output,json.dumps(result,indent=2)),
                             (args.summary,summary(result))):
        target=Path(filename);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(content)
    print(json.dumps({"games":len(result["games"]),"calibrated":False}))

if __name__=="__main__":
    main()
