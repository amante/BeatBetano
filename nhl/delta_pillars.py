"""NHL current-season evidence sheet from an immutable, timestamped snapshot.

Pure descriptive observations, never lineup-verified CRS or calibrated win probabilities.
"""
import argparse,json,math
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

SRC="https://api.nhle.com/stats/rest/en"
def number(x):
    return type(x) in (int,float) and math.isfinite(x)
def feature_sheet(snapshot):
    if snapshot.get("sport")!="nhl" or not snapshot.get("season") or not snapshot.get("as_of_utc"):
        raise ValueError("Missing NHL snapshot identity or timestamp")
    datetime.fromisoformat(snapshot["as_of_utc"].replace("Z","+00:00"))
    rows=snapshot["reports"]
    skaters=rows["skater/summary"];goalies=rows["goalie/summary"];teams=rows["team/summary"]
    if not skaters or not goalies or len(teams)!=32:raise ValueError("Incomplete snapshot")
    by_skaters=defaultdict(list);by_goalies=defaultdict(list)
    for p in skaters:
        for abbrev in str(p.get("teamAbbrevs","")).split(","):
            abbrev=abbrev.strip()
            if abbrev:by_skaters[abbrev].append(p)
    for p in goalies:
        for abbrev in str(p.get("teamAbbrevs","")).split(","):
            abbrev=abbrev.strip()
            if abbrev:by_goalies[abbrev].append(p)
    # ID mapping is restricted to the NHL Stats full team names; never guess.
    names={"Anaheim Ducks":"ANA","Boston Bruins":"BOS","Buffalo Sabres":"BUF",
    "Calgary Flames":"CGY","Carolina Hurricanes":"CAR","Chicago Blackhawks":"CHI",
    "Colorado Avalanche":"COL","Columbus Blue Jackets":"CBJ","Dallas Stars":"DAL",
    "Detroit Red Wings":"DET","Edmonton Oilers":"EDM","Florida Panthers":"FLA",
    "Los Angeles Kings":"LAK","Minnesota Wild":"MIN","Montréal Canadiens":"MTL",
    "Montreal Canadiens":"MTL","Nashville Predators":"NSH","New Jersey Devils":"NJD",
    "New York Islanders":"NYI","New York Rangers":"NYR","Ottawa Senators":"OTT",
    "Philadelphia Flyers":"PHI","Pittsburgh Penguins":"PIT","San Jose Sharks":"SJS",
    "Seattle Kraken":"SEA","St. Louis Blues":"STL","Tampa Bay Lightning":"TBL",
    "Toronto Maple Leafs":"TOR","Utah Mammoth":"UTA","Vancouver Canucks":"VAN",
    "Vegas Golden Knights":"VGK","Washington Capitals":"WSH","Winnipeg Jets":"WPG"}
    out={"season":snapshot["season"],"as_of_utc":snapshot["as_of_utc"],
       "source":SRC,"record_counts":{"skaters":len(skaters),"goalies":len(goalies),"teams":len(teams)},
       "odds_used":False,"calibrated":False,"teams":{}}
    for t in teams:
        abbrev=names.get(t.get("teamFullName"))
        if not abbrev:raise ValueError("Unmapped team name: "+str(t.get("teamFullName")))
        players=by_skaters[abbrev]
        defenders=[p for p in players if p.get("positionCode")=="D"]
        forwards=[p for p in players if p.get("positionCode") in ("C","L","R")]
        def group(items):
            return {"players_with_stats":len(items),"points_sum":sum(p.get("points",0) or 0 for p in items),
              "goals_sum":sum(p.get("goals",0) or 0 for p in items),
              "members": [{"player_id":p.get("playerId"),"name":p.get("skaterFullName"),
                 "games_played":p.get("gamesPlayed"),"points":p.get("points"),
                 "toi_per_game_seconds":p.get("timeOnIcePerGame")} for p in items]}
        gl=[{"player_id":g.get("playerId"),"name":g.get("goalieFullName"),
             "games_started":g.get("gamesStarted"),"shots_against":g.get("shotsAgainst"),
             "saves":g.get("saves"),"save_pct_observed":g.get("savePct")} for g in by_goalies[abbrev]]
        out["teams"][abbrev]={
          "name":t["teamFullName"],"team_id":t["teamId"],
          "crs_evidence":{"games_played":t.get("gamesPlayed"),
              "goals_for_per_game":t.get("goalsForPerGame"),"goals_against_per_game":t.get("goalsAgainstPerGame"),
              "shots_for_per_game":t.get("shotsForPerGame"),"shots_against_per_game":t.get("shotsAgainstPerGame"),
              "current_roster_confirmed":False,"rating":None},
          "unit_evidence":{"forwards":group(forwards),"defense":group(defenders),
               "lines_confirmed":False,"rating":None},
          "goalie_evidence":{"candidates":gl,"starter_confirmed":False,"goalie_daily_rating":None},
          "special_teams_evidence":{"power_play_pct_observed":t.get("powerPlayPct"),
              "penalty_kill_pct_observed":t.get("penaltyKillPct"),
              "opportunities_verified":False,"bayesian_pp_strength":None,"bayesian_pk_strength":None}}
    return out
def markdown(sheet):
    lines=["## NHL 2026–27 — current observations for four model pillars","",
      "Snapshot: "+sheet["as_of_utc"],"",
      "**Not calibrated:** no verified current lineups, confirmed starters or trained win probabilities.","",
      "| Team | Forwards | Defenders | Goalie candidates | GF/G | GA/G | PP% | PK% |",
      "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for team,x in sorted(sheet["teams"].items()):
        c=x["crs_evidence"];u=x["unit_evidence"];g=x["goalie_evidence"];s=x["special_teams_evidence"]
        fmt=lambda v:round(v,3) if number(v) else "—"
        lines.append(f'| {team} | {u["forwards"]["players_with_stats"]} | {u["defense"]["players_with_stats"]} | {len(g["candidates"])} | {fmt(c["goals_for_per_game"])} | {fmt(c["goals_against_per_game"])} | {fmt(s["power_play_pct_observed"])} | {fmt(s["penalty_kill_pct_observed"])} |')
    return "\n".join(lines)+"\n"
def main():
    p=argparse.ArgumentParser();p.add_argument("--input",required=True);p.add_argument("--output",required=True);p.add_argument("--summary",required=True)
    a=p.parse_args();sheet=feature_sheet(json.loads(Path(a.input).read_text()))
    for dest,body in ((a.output,json.dumps(sheet,indent=2)),(a.summary,markdown(sheet))):
        path=Path(dest);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body)
    print(json.dumps({"teams":len(sheet["teams"]),"records":sheet["record_counts"],"calibrated":False}))
if __name__=="__main__":main()
