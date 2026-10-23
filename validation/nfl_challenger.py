"""NFL odds-free rolling-form challenger. NOT EPA, NOT official 2026–27 model.

Features are generated strictly before each game; one fixed train/test split:
train 2013–2023, evaluate 2024–2025. Same-day scores never leak.
"""
import argparse, json
from collections import defaultdict, deque
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

def build_features(data):
    required={"season","gameday","home_team","away_team","home_score","away_score"}
    missing=required-set(data.columns)
    if missing: raise ValueError(f"Missing columns: {sorted(missing)}")
    d=data.dropna(subset=list(required)).copy()
    if "game_type" in d: d=d[d.game_type.isin(["REG","WC","DIV","CON","SB"])]
    d["date"]=pd.to_datetime(d.gameday,errors="coerce")
    d=d.dropna(subset=["date"]).sort_values(["season","date"])
    history=defaultdict(lambda:deque(maxlen=8))
    played={}
    rows=[]
    for (season,date),batch in d.groupby(["season","date"],sort=True):
        updates=[]
        for r in batch.itertuples():
            if r.home_score==r.away_score: continue
            h,a=r.home_team,r.away_team
            def stats(team):
                prior=history[team]
                # shrink small samples to league-neutral level
                n=len(prior)
                scored=(sum(v[0] for v in prior)+2*22)/(n+2)
                allowed=(sum(v[1] for v in prior)+2*22)/(n+2)
                return scored,allowed
            hs,ha=stats(h);as_,aa=stats(a)
            # capped rest days, first game uses neutral seven days
            def rest(team):
                if team not in played: return 7.
                return float(max(0,min(21,(date-played[team]).days)))
            rows.append({"season":int(season),"date":str(date.date()),"home":h,"away":a,
                         "form_net_diff":(hs-ha)-(as_-aa),
                         "attack_diff":hs-as_,"defense_diff":aa-ha,
                         "rest_diff":rest(h)-rest(a),
                         "home_win":int(r.home_score>r.away_score)})
            updates.append((h,a,float(r.home_score),float(r.away_score)))
        # End-of-day updates; no prediction sees a game from its own date.
        for h,a,score_h,score_a in updates:
            history[h].append((score_h,score_a))
            history[a].append((score_a,score_h))
            played[h]=date;played[a]=date
    return pd.DataFrame(rows)

def run(games_path,elo_path,out_path):
    feats=build_features(pd.read_csv(games_path,low_memory=False))
    if feats.empty: raise ValueError("No games to model")
    train=feats[(feats.season>=2013)&(feats.season<=2023)]
    test=feats[feats.season.isin([2024,2025])].copy()
    if len(train)<1000 or len(test)<400:
        raise ValueError(f"Insufficient train/test rows: {len(train)}/{len(test)}")
    feature_cols=["form_net_diff","attack_diff","defense_diff","rest_diff"]
    clf=make_pipeline(StandardScaler(),LogisticRegression(C=0.25,max_iter=2000,random_state=0))
    clf.fit(train[feature_cols],train.home_win)
    test["p_challenger"]=clf.predict_proba(test[feature_cols])[:,1]
    elo=pd.read_csv(elo_path)
    join=["season","date","home","away"]
    joined=test.merge(elo[join+["p_home","home_win"]],on=join,how="inner",validate="one_to_one")
    if len(joined)!=len(test): raise ValueError(f"Unmatched comparisons: {len(joined)} of {len(test)}")
    if not (joined.home_win_x==joined.home_win_y).all(): raise ValueError("Mismatched outcomes")
    y=joined.home_win_x.to_numpy(dtype=float)
    def score(p):
        p=np.clip(np.asarray(p,dtype=float),1e-8,1-1e-8)
        return {"brier":float(np.mean((p-y)**2)),"log_loss":float(np.mean(-y*np.log(p)-(1-y)*np.log1p(-p)))}
    base=score(joined.p_home);chall=score(joined.p_challenger)
    report={"description":"Rolling scoring-form logistic challenger vs Elo baseline; NOT EPA or official",
            "train_seasons":[2013,2023],"test_seasons":[2024,2025],
            "train_games":len(train),"test_games":len(joined),
            "elo":base,"challenger":chall,
            "delta_brier_challenger_minus_elo":chall["brier"]-base["brier"],
            "delta_log_loss_challenger_minus_elo":chall["log_loss"]-base["log_loss"]}
    output=Path(out_path);output.mkdir(parents=True,exist_ok=True)
    joined.to_csv(output/"paired_predictions.csv",index=False)
    (output/"comparison.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--games",required=True)
    parser.add_argument("--elo-predictions",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    run(args.games,args.elo_predictions,args.output)
