"""#271: fail-closed research deployment gate from held-out ablation evidence.

Ablation cannot promote goalie-conditioning when team-only performs better.
Source snapshots, richer baseline #218 and point-in-time readiness are still
unverified: never declare an official NHL model from this report.
"""
import argparse,json,math
from pathlib import Path
REQUIRED=("constant","teams","goalies","combined")
def gate(report):
    if report.get("kind")!="nhl_goalie_ablation_270" or report.get("odds_used") is not False:
        raise ValueError("Invalid research ablation")
    groups=report.get("groups",{})
    if set(groups)!=set(REQUIRED):raise ValueError("Incomplete four-arm ablation")
    n=report.get("holdout_n")
    if type(n) is not int or n<100:raise ValueError("Insufficient holdout")
    metrics={}
    for name in REQUIRED:
        values=groups[name]["holdout"]
        if values.get("n")!=n:raise ValueError("Unaligned holdouts")
        metrics[name]={}
        for metric in ("brier","log_loss"):
            value=values[metric]
            if type(value) not in (int,float) or not math.isfinite(value) or value<0:
                raise ValueError("Invalid metric")
            metrics[name][metric]=value
    eligible=lambda candidate,base: all(metrics[candidate][m]<metrics[base][m] for m in ("brier","log_loss"))
    team_gain=eligible("teams","constant")
    goalie_gain=eligible("combined","teams")
    return {"kind":"nhl_ml_research_decision_271","holdout_n":n,
            "team_vs_constant_improves_both":team_gain,
            "goalie_incremental_improves_both":goalie_gain,
            "research_candidate":"teams_only" if team_gain else None,
            "goalie_conditioning_status":"blocked_no_incremental_value" if not goalie_gain else "research_candidate_only",
            "strong_baseline_218_comparison":"not_yet_executed",
            "point_in_time_feature_proof":"not_yet_verified",
            "official_predictions":0,"production_approved":False,"automatic_promotion":False,
            "reason":"Strong matchup baseline and historical pregame availability not independently validated",
            "metric_values":metrics}
def main():
    p=argparse.ArgumentParser();p.add_argument("--ablation",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();result=gate(json.loads(Path(a.ablation).read_text()))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=="__main__":main()
