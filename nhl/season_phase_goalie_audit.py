"""NHL season-phase ML diagnostic and goalie sign sensitivity; research only.

Counts appearances per team, resets at each NHL season (July-Jun), and
freezes all same-day fixtures before updating counts. No odds or promotion.
"""
import argparse,json,math,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from historical_target_walkforward import read_labels,timeline,TEST_START,TUNE_START,TUNE_END,season
from prior_stats_ml_ablations import prepare,probability
from schedule_context_ablations import context,adjust,scoring

def phase_counts(labels):
    days=defaultdict(list)
    for r in labels:days[r["date"]].append(r)
    counts=defaultdict(int);result={}
    for day in sorted(days):
        for r in days[day]:
            s=season(r);h=counts[(s,r["home"])]+1;a=counts[(s,r["away"])]+1
            def phase(n):return "opening_1_10" if n<=10 else "developing_11_25" if n<=25 else "established_26_plus"
            # Same matchup can pair teams in different phases: report BOTH.
            result[r["game_id"]]={"home_game_number":h,"away_game_number":a,
                "home_phase":phase(h),"away_phase":phase(a),
                "both_phase":phase(h) if phase(h)==phase(a) else "mixed"}
        for r in days[day]:
            s=season(r);counts[(s,r["home"])]+=1;counts[(s,r["away"])]+=1
    return result

def errors(rows,features,contexts,cc,goalie,skater):
    out=[]
    for r in rows:
        base=adjust(r["probs"]["ml"][0],contexts[r["game_id"]],cc)
        p=probability(base,features[r["game_id"]],{"goalie":goalie,"skater":skater})
        y=int(r["y"]["ml"]=="home")
        out.append((r["game_id"],(p-y)**2,-math.log(max(1e-12,p if y else 1-p))))
    return out

def average(items):
    if not items:return {"n":0,"brier":None,"log_loss":None}
    return {"n":len(items),"brier":round(sum(x[1] for x in items)/len(items),6),
            "log_loss":round(sum(x[2] for x in items)/len(items),6)}

def evaluate(labels,observations):
    evidence=prepare(labels,observations);phases=phase_counts(labels)
    predictions=timeline(labels,80,.5);contexts=context(labels)
    tune=[r for r in predictions if TUNE_START<=r["date"]<=TUNE_END]
    test=[r for r in predictions if r["date"]>=TEST_START]
    if len(test)!=554:raise ValueError("Holdout not the expected 554 games")
    grid=(-.06,-.03,0.,.03,.06)
    cc=min(((r,d,v) for r in grid for d in grid for v in grid),
           key=lambda c:(scoring(tune,contexts,c)["log_loss"],c))
    variants={"context_only":(0.,0.),"skater_only":(0.,.2),
              "goalie_negative":(-4.,.2),"goalie_zero":(0.,.2),
              "goalie_positive":(4.,.2)}
    outputs={name:errors(test,evidence,contexts,cc,*coeff) for name,coeff in variants.items()}
    # Compare fixed coefficients: the holdout is descriptive, never select winners here.
    periods=sorted(set(phases[r["game_id"]]["both_phase"] for r in test))
    byphase={}
    for p in periods:
        ids={r["game_id"] for r in test if phases[r["game_id"]]["both_phase"]==p}
        byphase[p]={"games":len(ids),"variants":{name:average([item for item in output if item[0] in ids]) for name,output in outputs.items()}}
    season_groups=defaultdict(list)
    for r in test:season_groups[str(season({"date":r["date"]}))].append(r["game_id"])
    byseason={s:{"games":len(ids),"variants":{name:average([x for x in output if x[0] in set(ids)]) for name,output in outputs.items()}}
              for s,ids in sorted(season_groups.items())}
    return {"source_games":len(labels),"holdout_games":len(test),"tune_window":[TUNE_START,TUNE_END],
            "test_from":TEST_START,"season_definition":"NHL season starts July 1; team game ordinal derived from earlier or same-date fixture count, no outcomes",
            "phase_definition":{"opening_1_10":"games 1-10 per team","developing_11_25":"games 11-25 per team","established_26_plus":"games 26+"},
            "context_coefficients":list(cc),
            "fixed_goalie_sensitivity_coefficients":[-4.,0.,4.],"fixed_skater_coefficient":.2,
            "holdout_variants":{name:average(output) for name,output in outputs.items()},
            "same_phase_comparison":byphase,"season_comparison":byseason,
            "holdout_used_for_selection":False,"no_independent_confirmation":True,
            "starter_confirmed":False,"odds_used":False,"official_model_promoted":False,
            "warnings":["Goalie save percentage is a prior TEAM aggregate, not a starter forecast.",
                        "The 554-game holdout has been examined before; sensitivity is exploratory.",
                        "Phase uses both teams' game ordinal; mixed phases are explicitly retained.",
                        "No same-game outcome enters phase labels."]}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--labels",required=True);p.add_argument("--features",required=True);p.add_argument("--output",required=True)
    a=p.parse_args()
    result=evaluate(read_labels(a.labels),json.loads(Path(a.features).read_text()))
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=="__main__":main()
