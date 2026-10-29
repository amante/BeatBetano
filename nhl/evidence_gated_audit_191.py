"""#191 evidence-gated NHL research audit. Never promotes an official model.

The historical context ablation (186) uses only lagged schedules. New modules
must have independent point-in-time evidence; no missing-to-zero substitution.
The holdout in 186 was previously examined, not an independent prospective test.
"""
import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

try:
    from nhl.integrated_ablation_audit_186 import evaluate
    from nhl.historical_target_walkforward import read_labels
except ModuleNotFoundError:
    from integrated_ablation_audit_186 import evaluate
    from historical_target_walkforward import read_labels

MODULES = ("fatigue", "division_rivalry", "special_teams", "availability_delta")
REQUIRED = {
    "fatigue": ("rest_differential",),
    "division_rivalry": ("division", "rivalry_tier"),
    "special_teams": ("home_pp", "away_pp", "home_pk", "away_pk"),
    "availability_delta": ("home_roster_delta", "away_roster_delta"),
}

def validate_manifest(manifest, labels):
    """Only verified pregame observations count toward data coverage."""
    games = {str(x["game_id"]): x for x in labels}
    seen = set()
    counts = {m: 0 for m in MODULES}
    exclusions = {m: {} for m in MODULES}
    for item in manifest:
        game_id = str(item["game_id"])
        if game_id in seen:
            raise ValueError("Duplicate manifest game_id")
        seen.add(game_id)
        if game_id not in games:
            raise ValueError("Manifest fixture not present in labels")
        target_date = date.fromisoformat(games[game_id]["date"])
        observed_date = date.fromisoformat(item["target_date"])
        if observed_date != target_date:
            raise ValueError("Manifest target_date mismatch")
        for module in MODULES:
            node = item.get("modules", {}).get(module)
            reason = None
            if not isinstance(node, dict):
                reason = "no_record"
            elif not node.get("source") or not node.get("recorded_at"):
                reason = "no_source_or_timestamp"
            else:
                timestamp = datetime.fromisoformat(node["recorded_at"].replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    raise ValueError("Naive timestamps are not permitted")
                if timestamp.astimezone(timezone.utc).date() >= target_date:
                    reason = "not_strictly_prior_date"
                elif any(node.get(k) is None for k in REQUIRED[module]):
                    reason = "missing_required_fields"
                elif module == "availability_delta" and not (
                    node.get("baseline_source") and node.get("expected_source")
                    and node.get("baseline_as_of") and node.get("expected_as_of")
                ):
                    reason = "missing_roster_provenance"
                elif module == "special_teams" and not node.get("sourced_observations"):
                    reason = "missing_observation_provenance"
            if reason:
                exclusions[module][reason] = exclusions[module].get(reason, 0) + 1
            else:
                counts[module] += 1
    denominator = len(games)
    return {
        module: {
            "verified_n": counts[module],
            "archive_n": denominator,
            "coverage": round(counts[module] / denominator, 6) if denominator else None,
            "exclusions": exclusions[module],
            "predictive_effect": None,
            "status": "coverage_only_not_predictive_validation"
        } for module in MODULES
    }

def audit(labels, manifest=()):
    result = evaluate(labels)
    result["pr191"] = {
        "coverage": validate_manifest(manifest, labels),
        "evaluated_modules": ["fatigue_schedule_proxy", "division", "rivalry_tier_a"],
        "not_automatically_evaluable": ["special_teams", "availability_delta"],
        "brier_logloss": result["difference_vs_baseline_ml"],
        "calibration_status": "not_newly_estimated",
        "experimental_challenger": "not_executed_without_point_in_time_predictions",
        "retrospective_holdout_previously_inspected": True,
        "prospective_independent_validation": False,
        "no_odds_used": True,
        "official_model_unchanged": True,
        "promote": False,
    }
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--labels", required=True)
    p.add_argument("--manifest")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    labels = read_labels(args.labels)
    manifest = json.loads(Path(args.manifest).read_text()) if args.manifest else []
    result = audit(labels, manifest)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps({"archive_n": result["archive_games"],
                      "coverage": result["pr191"]["coverage"],
                      "promotion": False}, indent=2))
if __name__ == "__main__":
    main()
