"""Auditable preliminary NHL roster ratings from strictly prior-date player observations.

NOT official CRS, matchup probabilities or validated player impact.
Expected lineup is required with a source and as-of timestamp. Missing player
data is flagged, never silently replaced with team averages.
"""
import argparse,json,math
from pathlib import Path
from datetime import datetime

UNITS=("top6","middle6","bottom6","top4_d","depth_d","goalie")
def timepoint(value):
    t=datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None:raise ValueError("Timezone required")
    return t

def validate(lineup,prediction_time,team):
    if not isinstance(lineup,dict) or lineup.get("team")!=team:raise ValueError("Team mismatch")
    if not lineup.get("source"):raise ValueError("Lineup source required")
    if timepoint(lineup["as_of"])>timepoint(prediction_time):raise ValueError("Future lineup snapshot")
    players=lineup.get("players")
    if not isinstance(players,list) or not players:raise ValueError("Empty expected lineup")
    seen=set()
    for player in players:
        pid=player.get("player_id")
        if not isinstance(pid,int) or pid<=0 or pid in seen:raise ValueError("Invalid/duplicate player id")
        seen.add(pid)
        if player.get("unit") not in UNITS:raise ValueError("Unrecognized deployment unit")
        if player.get("status") not in ("confirmed","projected","out"):raise ValueError("Invalid status")
        weight=player.get("expected_share")
        if not isinstance(weight,(int,float)) or isinstance(weight,bool) or not math.isfinite(weight) or not 0<=weight<=1:
            raise ValueError("Expected share must be within [0,1]")
        if player["status"]=="out" and weight!=0:raise ValueError("Unavailable player has positive deployment")
    return players

def player_level(record,role):
    if not record:return None
    n=record.get("observed",0)
    if role=="goalie":
        # Historical archive has IDs and appearances, but this stage does not
        # contain ID-linked goalie shot/save values: refuse goalie numeric score.
        return None
    if n<1:return None
    return {"past_observed_games":n,
        "goals_per_observed_game":round(record["goals"]/n,6),
        "shots_per_observed_game":round(record["shots"]/n,6),
        "data_scope":"past games with same TEAM only; no TOI, quality-adjustment or player causal isolation"}

def assess(past,lineup,prediction_time):
    players=validate(lineup,prediction_time,past["team"])
    units={k:{"expected_players":0,"historically_observed":0,"weighted_goals":0.,
              "weighted_shots":0.,"known_share":0.,"missing_player_ids":[]} for k in UNITS}
    excluded=[];per_player=[]
    for p in players:
        id=str(p["player_id"]);unit=p["unit"];status=p["status"]
        if status=="out":
            excluded.append(p["player_id"]);continue
        u=units[unit];u["expected_players"]+=1
        history=past["players"].get(id)
        role="goalie" if unit=="goalie" else "skater"
        lv=player_level(history,role)
        per_player.append({"player_id":p["player_id"],"unit":unit,"status":status,
                           "expected_share":p["expected_share"],"historical":lv})
        if lv is None:u["missing_player_ids"].append(p["player_id"]);continue
        share=p["expected_share"];u["historically_observed"]+=1;u["known_share"]+=share
        u["weighted_goals"]+=lv["goals_per_observed_game"]*share
        u["weighted_shots"]+=lv["shots_per_observed_game"]*share
    for k,u in units.items():
        share=u.pop("known_share")
        u["historic_weighted_goals_per_player_game"]=round(u.pop("weighted_goals")/share,6) if share else None
        u["historic_weighted_shots_per_player_game"]=round(u.pop("weighted_shots")/share,6) if share else None
        u["history_share_coverage"]=round(share/sum(p["expected_share"] for p in players if p["status"]!="out" and p["unit"]==k),4) if sum(p["expected_share"] for p in players if p["status"]!="out" and p["unit"]==k) else None
    return {"team":past["team"],"as_of":lineup["as_of"],"prediction_time":prediction_time,
      "source":lineup["source"],"units":units,"players":per_player,"excluded_ids":excluded,
      "crs_numeric_rating":None,"availability_delta":None,
      "interpretation":"Descriptive component evidence only: no full CRS, goalie rating, or predicted performance. Availability delta requires an independently sourced baseline lineup.",
      "odds_used":False,"model_promoted":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True);p.add_argument("--game-id",required=True)
    p.add_argument("--side",choices=("home","away"),required=True)
    p.add_argument("--lineup",required=True);p.add_argument("--prediction-time",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args();hist=json.loads(Path(a.history).read_text())
    selected=[x for x in hist if x["game_id"]==a.game_id]
    if len(selected)!=1:raise ValueError("Game ID not found uniquely")
    past=selected[0][a.side];lineup=json.loads(Path(a.lineup).read_text())
    result=assess(past,lineup,a.prediction_time)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2))
    print(json.dumps({"team":result["team"],"unit_coverage":{k:v["history_share_coverage"] for k,v in result["units"].items()},
                       "crs_numeric_rating":None,"availability_delta":None},indent=2))
if __name__=="__main__":main()
