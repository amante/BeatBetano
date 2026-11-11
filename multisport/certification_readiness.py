"""Publish model-specific certification readiness without overstating evidence."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from multisport.certification_gate import assess
from multisport.data_lineage import digest


BASE_BLOCKERS = [
    "two_independent_seasons_and_temporal_holdout_not_provided",
    "paired_baseline_and_ablation_walk_forward_not_provided",
    "training_data_and_model_code_lineage_not_attested",
    "independent_source_and_reliability_review_not_attested",
]


def build_status(evaluation, evidence_dir=None):
    groups = evaluation.get("groups", [])
    by_model = {}
    for group in groups:
        sport, version = group.get("sport"), group.get("model_version")
        if not sport or not version:
            continue
        key = (sport, version)
        row = by_model.setdefault(key, {"sport": sport, "model_version": version,
                                        "scored_forecasts": 0, "stages": []})
        metrics = group.get("metrics", {})
        row["scored_forecasts"] += int(metrics.get("n", 0))
        row["stages"].append({"stage": group.get("stage"), "n": int(metrics.get("n", 0))})

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
             and packet.get("scope", {}).get("sport") == key[0]
             and packet.get("scope", {}).get("model_version") == key[1]),
            None,
        )
        blockers = list(BASE_BLOCKERS)
        eligible = False
        packet_name = None
        if packet_entry:
            packet_name, packet = packet_entry
            try:
                gate = assess(packet)
                blockers = gate["reasons"]
                eligible = gate["eligible_for_certification_review"]
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
    parser.add_argument("--output", default="frontend/data/certification-readiness-latest.json")
    args = parser.parse_args()
    evaluation = json.loads(Path(args.evaluation).read_text())
    report = build_status(evaluation, args.evidence_dir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"models": report["scored_model_versions"], "certified": False}))


if __name__ == "__main__":
    main()
