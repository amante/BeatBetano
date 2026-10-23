"""Pre-game NFL EPA and success-rate challenger from historical play-by-play.
Prior games only. Team season rollover resets history; no betting odds.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES=["off_epa_diff","def_epa_diff","off_success_diff","def_success_diff","rest_diff"]
def build(games,pbp):
    required={"game_id","posteam","defteam","epa","success"}
    if not required.issubset(pbp.columns):
        raise ValueError(f"Missing PBP columns {sorted(required-set(pbp.columns))}")
    must={"game_id","season","gameday","home_team","away_team","home_score","away_score"}
    if not must.issubset(games.columns):
        raise ValueError(f"Missing game columns {sorted(must-set(games.columns))}")
    games=games.copy()
    games["date"]=pd.to_datetime(games.gameday)
    games=games.dropna(subset=["date","home_score","away_score"])
    games=games[games.home_score!=games.away_score].sort_values(["season","date","game_id"])
    pbp=pbp[pbp.game_id.isin(games.game_id)].copy()
    pbp=pbp[pbp.posteam.notna() & pbp.defteam.notna() & pbp.epa.notna() & pbp.success.notna()]
    if "play_type" in pbp: pbp=pbp[pbp.play_type.isin(["pass","run"])]
    if pbp.empty: raise ValueError("No eligible PBP plays")
    atk=pbp.groupby(["game_id","posteam"],as_index=False).agg(off_epa=("epa","mean"),off_success=("success","mean"))
    dfn=pbp.groupby(["game_id","defteam"],as_index=False).agg(def_epa_allowed=("epa","mean"),def_success_allowed=("success","mean"))
    per_game={}
    for r in atk.itertuples():per_game.setdefault(r.game_id,{}).setdefault(r.posteam,{}).update(off_epa=r.off_epa,off_success=r.off_success)
    for r in dfn.itertuples():per_game.setdefault(r.game_id,{}).setdefault(r.defteam,{}).update(def_epa_allowed=r.def_epa_allowed,def_success_allowed=r.def_success_allowed)
    history={};last_seen={};previous_season=None;rows=[]
    def average(team,key,default):
        values=[v[key] for v in history.get(team,[]) if key in v]
        return (sum(values)+4*default)/(len(values)+4)
    for (season,date),batch in games.groupby(["season","date"],sort=True):
        if previous_season is not None and season!=previous_season:
            history={};last_seen={}
        previous_season=season
        changes=[]
        for r in batch.itertuples():
            a,h=r.away_team,r.home_team
            metrics_a=per_game.get(r.game_id,{}).get(a)
            metrics_h=per_game.get(r.game_id,{}).get(h)
            if metrics_a is None or metrics_h is None:continue
            def rest(t):return min(21,max(0,(date-last_seen[t]).days)) if t in last_seen else 7
            rows.append({"season":int(season),"date":str(date.date()),"home":h,"away":a,
                "off_epa_diff":average(h,"off_epa",0)-average(a,"off_epa",0),
                "def_epa_diff":average(a,"def_epa_allowed",0)-average(h,"def_epa_allowed",0),
                "off_success_diff":average(h,"off_success",.43)-average(a,"off_success",.43),
                "def_success_diff":average(a,"def_success_allowed",.43)-average(h,"def_success_allowed",.43),
                "rest_diff":rest(h)-rest(a),"home_win":int(r.home_score>r.away_score)})
            changes.append((h,a,metrics_h,metrics_a))
        for h,a,mh,ma in changes:
            for team,stats in [(h,mh),(a,ma)]:
                history.setdefault(team,[]).append(stats)
                history[team]=history[team][-8:]
                last_seen[team]=date
    result=pd.DataFrame(rows)
    if result.empty:raise ValueError("No matched games with PBP data")
    return result

def compare(games_path,pbp_path,elo_path,out):
    games=pd.read_csv(games_path,low_memory=False)
    pbp=pd.read_parquet(pbp_path)
    features=build(games,pbp)
    train=features[(features.season>=2013)&(features.season<=2023)]
    test=features[features.season.isin([2024,2025])]
    if len(train)<1000 or len(test)<400:raise ValueError(f"Insufficient data: {len(train)} train / {len(test)} test")
    model=make_pipeline(StandardScaler(),LogisticRegression(C=.2,max_iter=1500,random_state=0))
    model.fit(train[FEATURES],train.home_win)
    test=test.copy();test["p_challenger"]=model.predict_proba(test[FEATURES])[:,1]
    elo=pd.read_csv(elo_path)
    join=["season","date","home","away"]
    pairs=test.merge(elo[join+["p_home","home_win"]],on=join,validate="one_to_one")
    if len(pairs)!=len(test):raise ValueError("Missing Elo comparison games")
    if not (pairs.home_win_x==pairs.home_win_y).all():raise ValueError("Outcome mismatch")
    y=pairs.home_win_x.to_numpy()
    def score(p):
        p=np.clip(np.asarray(p),1e-9,1-1e-9)
        return {"brier":float(np.mean((p-y)**2)),"log_loss":float(np.mean(-y*np.log(p)-(1-y)*np.log1p(-p)))}
    baseline=score(pairs.p_home);challenger=score(pairs.p_challenger)
    report={"model":"EPA/success rolling logistic (not official)","train_games":len(train),
            "test_games":len(pairs),"test_seasons":[2024,2025],
            "elo":baseline,"challenger":challenger,
            "delta_brier":challenger["brier"]-baseline["brier"],
            "delta_log_loss":challenger["log_loss"]-baseline["log_loss"]}
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    pairs.to_csv(out/"paired_predictions.csv",index=False)
    (out/"comparison.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--games",required=True);p.add_argument("--pbp",required=True)
    p.add_argument("--elo",required=True);p.add_argument("--output",required=True)
    a=p.parse_args();compare(a.games,a.pbp,a.elo,a.output)
