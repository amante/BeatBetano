"""Freeze post-protocol forecasts into sport/version/code-specific holdout cohorts."""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from multisport.data_lineage import digest
from multisport.forecast_evaluation import _forecast_chains, _forecast_versions, season_label


def _utc(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _prefix_allowed(sport, version, policy):
    prefixes = policy.get("accepted_model_version_prefixes", {}).get(sport, [])
    return any(version == prefix or version.startswith(prefix) for prefix in prefixes)


def _lineage_complete(item):
    provenance = item.get("model_provenance") or {}
    code_hash = provenance.get("model_code_sha256")
    has_code_hash = isinstance(code_hash, str) and len(code_hash) == 64
    has_code_revision = bool(provenance.get("model_code_revision"))
    training = bool(provenance.get("training_data_sha256") and provenance.get("training_cutoff_utc"))
    point_in_time = bool(provenance.get("predictor_input_sha256") and provenance.get("predictor_input_as_of_utc"))
    return has_code_hash and has_code_revision and (training or point_in_time)


def capture(archive, policy, evaluation=None):
    frozen_at = _utc(policy["frozen_at_utc"])
    chains, chain_issues, _ = _forecast_chains(archive)
    selected, forecast_issues = _forecast_versions(chains)
    rejected = Counter()
    grouped = defaultdict(lambda: {"events": set(), "lineage_complete_events": set(),
                                   "by_season": defaultdict(lambda: {"frozen_forecasts": 0,
                                                                     "lineage_complete_forecasts": 0})})
    for item in selected:
        sport, event, version = item["sport"], item["event"], item["model_version"]
        emitted = _utc(item["emitted_at_utc"])
        try:
            start = _utc(event["start_utc"])
        except (KeyError, TypeError, ValueError):
            rejected["invalid_start_time"] += 1
            continue
        if emitted < frozen_at:
            rejected["emitted_before_protocol_freeze"] += 1
            continue
        provenance=item.get("model_provenance") or {}
        if emitted >= start or _utc(provenance.get("predictor_input_as_of_utc", item["emitted_at_utc"])) >= start:
            # The snapshot verifier already enforces pregame emission. This second check
            # catches a declared predictor input observed after the fixture began.
            rejected["not_point_in_time"] += 1
            continue
        if not _prefix_allowed(sport, version, policy):
            rejected["model_version_outside_protocol"] += 1
            continue
        code_hash = item.get("model_code_sha256")
        key = (sport, version, code_hash)
        season = season_label(sport, event["start_utc"])
        bucket = grouped[key]
        event_id = str(event["event_id"])
        if event_id not in bucket["events"]:
            bucket["events"].add(event_id)
            bucket["by_season"][season]["frozen_forecasts"] += 1
        if _lineage_complete(item) and event_id not in bucket["lineage_complete_events"]:
            bucket["lineage_complete_events"].add(event_id)
            bucket["by_season"][season]["lineage_complete_forecasts"] += 1

    scored_index = {}
    for group in (evaluation or {}).get("groups", []):
        key = (group.get("sport"), group.get("model_version"), group.get("model_code_sha256"))
        if key not in grouped:
            continue
        scored_index[key] = {
            season: int(metrics.get("n", 0))
            for season, metrics in group.get("by_season", {}).items()
        }

    exclusions=Counter(chain_issues)
    exclusions.update(forecast_issues)
    exclusions.update(rejected)
    models = []
    for (sport, version, code_hash), row in sorted(grouped.items()):
        by_season = {}
        for season, counts in sorted(row["by_season"].items()):
            by_season[season] = {
                **counts,
                "settled_forecasts_scored": scored_index.get((sport, version, code_hash), {}).get(season, 0),
            }
        mature = sum(
            counts["settled_forecasts_scored"] >= policy["minimum_settled_forecasts_per_season"]
            for counts in by_season.values()
        ) >= policy["minimum_holdout_seasons"]
        models.append({
            "sport": sport,
            "model_version": version,
            "model_code_sha256": code_hash,
            "frozen_forecasts": len(row["events"]),
            "lineage_complete_forecasts": len(row["lineage_complete_events"]),
            "by_season": by_season,
            "minimum_holdout_seasons": policy["minimum_holdout_seasons"],
            "minimum_settled_forecasts_per_season": policy["minimum_settled_forecasts_per_season"],
            "holdout_sample_mature": mature,
            "certified": False,
        })
    return {
        "schema_version": 1,
        "kind": "prospective_certification_holdout_cohorts",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_id": policy["protocol_id"],
        "protocol_frozen_at_utc": policy["frozen_at_utc"],
        "protocol_sha256": digest(policy),
        "inputs": {
            "verified_chains": len(chains),
            "valid_pregame_model_emissions": len(selected),
            "history_sha256": digest((evaluation or {}).get("inputs", {})),
        },
        "models": models,
        "rejected_counts": dict(sorted(exclusions.items())),
        "certified": False,
        "automatic_promotion_allowed": False,
        "note": "Counts reflect frozen forecast coverage. A mature cohort is only sample-size readiness; it is not an independent review or certification.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", default="frontend/data/forecast_archive")
    parser.add_argument("--protocol", default="multisport/certification_holdout_protocol.json")
    parser.add_argument("--evaluation", default="frontend/data/forecast-evaluation-latest.json")
    parser.add_argument("--output", default="frontend/data/forecast-holdout-latest.json")
    args = parser.parse_args()
    protocol = json.loads(Path(args.protocol).read_text())
    evaluation = json.loads(Path(args.evaluation).read_text())
    report = capture(args.archive, protocol, evaluation)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"models": len(report["models"]), "certified": False}))


if __name__ == "__main__":
    main()
