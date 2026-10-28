"""Evidence classification of NHL historical gamecenter records.

Postgame boxscores can document previous games; they never prove what was
confirmed before the *same* game. This audits coverage without imputations.
"""
import argparse,json,hashlib
from collections import Counter
from pathlib import Path

MODULES=("goalie","roster","special_teams")
def is_nonempty(v):
    return isinstance(v,(dict,list)) and bool(v)

def inspect(game):
    box=game.get("boxscore") or {}
    stats=box.get("player_by_game_stats")
    home=box.get("home_team") or {}
    away=box.get("away_team") or {}
    def any_stats(side):
        return isinstance(stats,dict) and is_nonempty(stats.get(side+"Team"))
    # Official playerByGameStats is a postgame observation, NOT a pregame roster.
    player_stats=is_nonempty(stats)
    known_team_ids=home.get("id") is not None and away.get("id") is not None
    # Explicitly require structured specialty stats; don't confuse a goalie
    # roster appearance or a team boxscore with confirmed starter / PP rates.
    goalie_observed=False
    if isinstance(stats,dict):
        for side in ("homeTeam","awayTeam"):
            entry=stats.get(side) or {}
            if isinstance(entry,dict) and is_nonempty(entry.get("goalies")):
                goalie_observed=True
    return {"boxscore_player_stats":player_stats,
            "boxscore_official_team_ids":known_team_ids,
            "goalie_postgame_appearances":goalie_observed,
            "roster_postgame_appearances":player_stats,
            "special_teams_pregame_snapshot":False,
            "confirmed_starter_at_tipoff":False,
            "dated_roster_at_tipoff":False,
            "dated_pp_pk_at_tipoff":False}

def audit(root,expected=2811):
    root=Path(root)
    files=sorted(p for p in root.glob("*.json") if p.name!="manifest.json")
    if len(files)!=expected:raise ValueError(f"Expected {expected} individual records, found {len(files)}")
    counts=Counter();seen=set();examples={}
    for path in files:
        game=json.loads(path.read_text())
        gid=str(game.get("game_id",""))
        if gid!=path.stem or not gid or gid in seen:raise ValueError("Missing/duplicate game identity")
        seen.add(gid)
        observed=inspect(game)
        for key,val in observed.items():
            if val:counts[key]+=1
            elif key not in examples:examples[key]=gid
    return {"source":"NHL official gamecenter, completed-game boxscore and PBP",
       "games":len(files),"coverage":{
          k:{"count":counts[k],"fraction":round(counts[k]/len(files),6),
             "example_absent_game":examples.get(k)}
          for k in ("boxscore_player_stats","boxscore_official_team_ids",
                    "goalie_postgame_appearances","roster_postgame_appearances",
                    "special_teams_pregame_snapshot","confirmed_starter_at_tipoff",
                    "dated_roster_at_tipoff","dated_pp_pk_at_tipoff")},
       "module_readiness":{
          "goalie":{"postgame_appearances_available":counts["goalie_postgame_appearances"],
                    "same_game_confirmed_starters_verified":0,"status":"blocked_confirmed_starter_timestamps"},
          "current_roster_strength":{"postgame_player_stats_available":counts["roster_postgame_appearances"],
                    "same_game_pregame_roster_verified":0,"status":"blocked_dated_lineup_and_injuries"},
          "special_teams":{"pregame_pp_pk_snapshots_verified":0,
                           "status":"blocked_dated_pp_pk_and_opponent_adjustment"}},
       "valid_next_research":"Compute prior-game-only observations by joining earlier dated games, but explicitly separate appearance evidence from starter confirmation.",
       "not_a_full_model_validation":True,"odds_used":False,
       "model_promotion_authorized":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",required=True);p.add_argument("--expected",type=int,default=2811)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    result=audit(args.archive,args.expected)
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
