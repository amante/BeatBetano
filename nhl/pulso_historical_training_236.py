"""Historical outcome-linked TEAM performance dataset, strictly prior-date features.

Research only. Team goalie rate is NOT the confirmed match goalie.
POSTGAME targets never enter the feature vectors.
"""
import argparse,csv,hashlib,json,math
from collections import Counter
from pathlib import Path
FEATURES=("prior_goalie_save_pct","prior_goalie_shots_against",
          "prior_skater_goals_per_observed_game","prior_skater_shots_per_observed_game",
          "past_games","past_goalie_observation_games","past_skater_observation_games")
TARGETS=("ml_winner","rt_result","home_reached_plus3","away_reached_plus3","first_to_plus3")

def build(history,labels,expected=None):
    if expected is not None and (len(history)!=expected or len(labels)!=expected):
        raise ValueError("Unexpected history/label row counts")
    identities={}
    for item in labels:
        gid=str(item.get("game_id",""))
        if not gid or gid in identities:raise ValueError("Missing/duplicate label ID")
        if item.get("data_class")!="POSTGAME_LABELS_NOT_PREGAME_FEATURES":
            raise ValueError("Unattested postgame target source")
        identities[gid]=item
    rows=[];seen=set();coverage=Counter();per_year=Counter()
    for source in history:
        gid=str(source.get("game_id",""))
        if not gid or gid in seen:raise ValueError("Missing/duplicate historical game ID")
        seen.add(gid)
        label=identities.get(gid)
        if label is None:raise ValueError("Missing historical label for "+gid)
        if source.get("source_class")!="earlier_dates_postgame_boxscores_only":
            raise ValueError("Historical source is not prior-date")
        if source["date"]!=label["date"]:raise ValueError("Date mismatch for "+gid)
        if not label["home"] or not label["away"] or label["home"]==label["away"]:
            raise ValueError("Invalid team identities")
        sides={}
        for side in ("home","away"):
            rec=source.get(side)
            if not isinstance(rec,dict):raise ValueError("Missing historical team vector")
            vector={}
            for key in FEATURES:
                value=rec.get(key)
                if value is not None:
                    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                        raise ValueError("Invalid prior performance value: "+key)
                    if key=="prior_goalie_save_pct" and value>1:raise ValueError("Goalie rate out of bounds")
                    coverage[side+"_"+key]+=1
                vector[key]=value
            if rec.get("pregame_starter_confirmed") is not False or rec.get("pregame_roster_confirmed") is not False:
                raise ValueError("Unverified starter or roster claim")
            sides[side]=vector
        ml=label["ml_winner"];rt=label["rt_result"]
        if ml not in ("home","away") or rt not in ("home","away","draw"):
            raise ValueError("Invalid historical result label")
        target={key:label[key] for key in TARGETS}
        rows.append({"game_id":gid,"date":source["date"],"home":label["home"],"away":label["away"],
                     "features":sides,"target":target})
        per_year[source["date"][:4]]+=1
    if set(identities)!=seen:raise ValueError("History and targets differ in game IDs")
    rows.sort(key=lambda x:(x["date"],x["game_id"]))
    counts={key:coverage[key] for side in ("home","away") for key in FEATURES for key in (side+"_"+key,)}
    both=sum(all(row["features"][side]["prior_goalie_save_pct"] is not None and
                 row["features"][side]["prior_skater_goals_per_observed_game"] is not None
                 for side in ("home","away")) for row in rows)
    manifest={"games":len(rows),"team_sides":len(rows)*2,"complete_core_feature_games":both,
              "feature_counts":counts,"games_by_calendar_year":dict(sorted(per_year.items())),
              "features_source":"prior-date official boxscores only",
              "target_source":"postgame official goal-event and final-score labels",
              "starter_confirmed":False,"lineup_confirmed":False,"odds_used":False,
              "official_model":False,"model_promoted":False,
              "note":"Team aggregates; no individual starting-goalie or pregame roster identities."}
    return {"status":"historical_team_research_dataset","rows":rows,"manifest":manifest}

def main():
    p=argparse.ArgumentParser()
    for key in ("history","labels","out","manifest"):p.add_argument("--"+key,required=True)
    p.add_argument("--expected",type=int,default=2811)
    a=p.parse_args()
    history=json.loads(Path(a.history).read_text())
    with Path(a.labels).open(newline="") as f:labels=list(csv.DictReader(f))
    result=build(history,labels,a.expected)
    output=Path(a.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result["rows"],indent=2))
    manifest=result["manifest"]
    manifest["sha256"]=hashlib.sha256(output.read_bytes()).hexdigest()
    Path(a.manifest).write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))
if __name__=="__main__":main()
