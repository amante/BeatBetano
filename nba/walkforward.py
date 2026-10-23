"""Honest NBA chronological Elo benchmark on three historical regular seasons.

Games must be sourced/verified separately. Predictions are made pre-update.
The first season warms up ratings; report holdout seasons independently.
"""
import argparse,json,sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from model import evaluate,score
from calibration_benchmark import compare_holdout

def evaluate_history(games):
    if not games:raise ValueError("No NBA games supplied")
    games=sorted(games,key=lambda x:(x["tipoff_utc"],str(x["game_id"])))
    if len({str(x["game_id"]) for x in games})!=len(games):
        raise ValueError("Repeated game IDs")
    seasons={int(x["season"]) for x in games}
    # ESPN season.year is typically the NBA end year.
    if not {2024,2025,2026}.issubset(seasons):
        raise ValueError(f"Require three full historical NBA seasons (ESPN end years); got {sorted(seasons)}")
    predictions=list(evaluate(games,season_min=2024,season_max=2026))
    byseason=defaultdict(list)
    for p,g in zip(predictions,games):
        byseason[p.season].append((p,g))
    summary={"source_game_count":len(games),"seasons":{},"training_season_end_year":2024,"holdout_years":[2025,2026]}
    for year in sorted(byseason):
        pg=byseason[year]
        summary["seasons"][str(year)]={
            "games":len(pg),
            "status":"warmup_not_holdout" if year==2024 else "holdout",
            **score([p for p,g in pg],[g for p,g in pg])
        }
    # Standard regular seasons contain 1,230 games each. Fail closed if incomplete.
    summary["coverage_verified"]=True
    summary["coverage_discrepancies"]={}
    for year in (2024,2025,2026):
        count=summary["seasons"][str(year)]["games"]
        if count!=1230:
            summary["coverage_verified"]=False
            summary["coverage_discrepancies"][str(year)]={"observed":count,"expected":1230,"difference":count-1230}
    summary["interpretation"]=("verified_game_count" if summary["coverage_verified"] else "EXPLORATORY_ONLY: ESPN game-count mismatches remain unreconciled; do not use as calibrated model")
    hold=[(p,g) for p,g in zip(predictions,games) if p.season in (2025,2026)]
    summary["holdout_pooled"]=score([p for p,g in hold],[g for p,g in hold])
    summary["benchmark_comparison"]=compare_holdout(predictions,games)
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",required=True)
    a=parser.parse_args()
    games=json.loads(Path(a.input).read_text())
    result=evaluate_history(games)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
