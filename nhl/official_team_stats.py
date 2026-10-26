"""NHL official prior-day standings-derived team form and special-teams observations.

A structured hockey feature module, not fitted CRS or goalie model. Source:
NHL standings as of a completed date; no bookmaker inputs.
"""
import math
FIELDS=("gamesPlayed","goalFor","goalAgainst","goalDifferential","powerPlayPct","penaltyKillPct")
def number(value):
    return type(value) in (int,float) and math.isfinite(value)
def collect(standings,source_url,observed_at_utc):
    if not source_url.startswith("https://api-web.nhle.com/v1/standings/"):
        raise ValueError("Official dated NHL standings URL required")
    rows={}
    for record in standings.get("standings",[]):
        team=record.get("teamAbbrev",{})
        team=team.get("default") if isinstance(team,dict) else team
        if not team:continue
        games=record.get("gamesPlayed")
        if type(games) is not int or games<0:continue
        stats={}
        for f in FIELDS:
            v=record.get(f)
            stats[f]=v if number(v) else None
        if all(stats[k] is not None for k in ("goalFor","goalAgainst")):
            stats["goal_diff_per_game_shrunk"]=(stats["goalFor"]-stats["goalAgainst"])/(games+10)
            stats["goals_for_per_game"]=stats["goalFor"]/games if games else None
            stats["goals_against_per_game"]=stats["goalAgainst"]/games if games else None
        else:
            stats["goal_diff_per_game_shrunk"]=None
            stats["goals_for_per_game"]=None
            stats["goals_against_per_game"]=None
        stats["power_play_pct_observed"]=stats["powerPlayPct"]
        stats["penalty_kill_pct_observed"]=stats["penaltyKillPct"]
        stats["sustainable_special_teams_strength"]=None
        stats["crs"]=None
        stats["goalie_rating"]=None
        stats["source_url"]=source_url
        stats["observed_at_utc"]=observed_at_utc
        rows[team]=stats
    return rows
