"""Publish model-specific certification readiness without overstating evidence."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from multisport.certification_gate import assess
from multisport.data_lineage import digest


BASE_BLOCKERS = [
    "paired_baseline_and_ablation_walk_forward_not_provided",
    "independent_source_and_reliability_review_not_attested",
]


def build_status(evaluation, evidence_dir=None, holdout=None):
    groups = evaluation.get("groups", [])
    by_model = {}
    for group in groups:
        sport, version = group.get("sport"), group.get("model_version")
        code_hash=group.get("model_code_sha256") or "missing"
        if not sport or not version:
            continue
        key = (sport, version, code_hash)
        row = by_model.setdefault(key, {"sport": sport, "model_version": version,
                                        "model_code_sha256":code_hash,
                                        "scored_forecasts": 0, "stages": [],"by_season":{},
                                        "lineage_coverage":{"scored_forecasts":0,
                                            "with_model_code_revision":0,
                                            "with_model_code_sha256":0,
                                            "with_training_data_sha256":0,
                                            "with_training_cutoff_utc":0,
                                            "with_predictor_input_sha256":0,
                                            "with_predictor_input_as_of_utc":0,
                                            "with_any_data_cutoff":0,
                                            "with_any_data_fingerprint":0}})
        metrics = group.get("metrics", {})
        n=int(metrics.get("n",0))
        row["scored_forecasts"] += n
        row["stages"].append({"stage": group.get("stage"), "n": n})
        for season,season_metrics in group.get("by_season",{}).items():
            row["by_season"][season]=row["by_season"].get(season,0)+int(season_metrics.get("n",0))
        coverage=group.get("lineage_coverage",{})
        for field in row["lineage_coverage"]:
            row["lineage_coverage"][field]+=int(coverage.get(field,0))

    holdout_index={
        (item.get("sport"),item.get("model_version"),item.get("model_code_sha256")):item
        for item in (holdout or {}).get("models",[])
    }

    packets = []
    if evidence_dir and Path(evidence_dir).exists():
        for path in sorted(Path(evidence_dir).glob("*.json")):
            try:
                packets.append((path.name, json.loads(path.read_text())))
            except (OSError, json.JSONDecodeError):
                packets.append((path.name, None))

    models = []
    for key, row in sorted(by_model.items()):
        packet_entry = next(
            ((name, packet) for name, packet in packets
             if isinstance(packet, dict)
             and isinstance(packet.get("scope"), dict)
             and packet["scope"].get("sport") == key[0]
             and packet["scope"].get("model_version") == key[1]
             and packet["scope"].get("model_code_sha256") == key[2]),
            None,
        )
        cohort=holdout_index.get(key,{})
        holdout_by_season=cohort.get("by_season",{})
        holdout_mature=cohort.get("holdout_sample_mature") is True
        row["holdout_by_season"]=holdout_by_season
        row["holdout_frozen_forecasts"]=cohort.get("frozen_forecasts",0)
        row["holdout_lineage_complete_forecasts"]=cohort.get("lineage_complete_forecasts",0)
        row["holdout_sample_mature"]=holdout_mature
        lineage=row["lineage_coverage"]
        source_cutoff_complete=lineage["with_any_data_cutoff"]==lineage["scored_forecasts"]
        data_fingerprint_complete=lineage["with_any_data_fingerprint"]==lineage["scored_forecasts"]
        lineage_complete=(lineage["scored_forecasts"]>0 and
            lineage["with_model_code_revision"]==lineage["scored_forecasts"] and
            lineage["with_model_code_sha256"]==lineage["scored_forecasts"] and
            source_cutoff_complete and data_fingerprint_complete)
        blockers = list(BASE_BLOCKERS)
        if not holdout_mature:
            blockers.append("prospective_holdout_sample_incomplete")
        if not lineage_complete:
            blockers.append("model_lineage_incomplete")
        eligible = False
        packet_name = None
        if packet_entry:
            packet_name, packet = packet_entry
            try:
                gate = assess(packet)
                blockers = sorted(set(blockers + gate["reasons"]))
                eligible = (gate["eligible_for_certification_review"] and
                            holdout_mature and lineage_complete)
            except (KeyError, TypeError, ValueError) as exc:
                blockers = ["invalid_certification_evidence_packet:" + str(exc)]
        else:
            blockers.append("certification_evidence_packet_missing")

        row.update({
            "eligible_for_certification_review": eligible,
            "certified": False,
            "automatic_promotion_allowed": False,
            "blockers": blockers,
            "evidence_packet": packet_name,
        })
        models.append(row)

    return {
        "schema_version": 1,
        "kind": "multisport_certification_readiness",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_sha256": digest(evaluation),
        "holdout_protocol_id": (holdout or {}).get("protocol_id"),
        "holdout_sha256": digest(holdout or {}),\n        "holdout_protocol_frozen_at_utc": (holdout or {}).get("protocol_frozen_at_utc"),
        "scored_model_versions": len(models),
        "models": models,
        "policy": {
            "holdout_seasons_minimum": 2,
            "games_per_season_minimum": 100,
            "required": [
                "protocol frozen before holdout",
                "paired baseline, challenger and declared ablations",
                "model code and training data lineage",
                "independent source, leakage and reliability review",
            ],
        },
        "certified": False,
        "automatic_promotion_allowed": False,
        "note": "This report distinguishes descriptive scores from certification evidence. Eligibility only requests human review and never certifies a model.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation", default="frontend/data/forecast-evaluation-latest.json")
    parser.add_argument("--evidence-dir", default="frontend/data/certification-evidence")
    parser.add_argument("--holdout", default="frontend/data/forecast-holdout-latest.json")
    parser.add_argument("--output", default="frontend/data/certification-readiness-latest.json")
    args = parser.parse_args()
    evaluation = json.loads(Path(args.evaluation).read_text())
    holdout = json.loads(Path(args.holdout).read_text()) if Path(args.holdout).exists() else {}
    report = build_status(evaluation, args.evidence_dir, holdout)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"models": report["scored_model_versions"], "certified": False}))


if __name__ == "__main__":
    main()
