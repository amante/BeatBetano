"""Score sealed, pregame forecast revisions against persisted final results.

This is descriptive postgame evaluation only. It never fits, calibrates, certifies,
selects, or promotes a model.
"""
import argparse
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from multisport.contract import SPORTS, utc
from multisport.data_lineage import digest
from multisport.forecast_revisions import verify_snapshot

FINAL_STATUSES = {
    "nba": {"STATUS_FINAL", "FINAL", "OFF"},
    "nfl": {"STATUS_FINAL", "FINAL", "OFF"},
    "nhl": {"STATUS_FINAL", "FINAL", "OFF"},
    "soccer": {"STATUS_FULL_TIME", "STATUS_FINAL", "FINAL"},
    "tennis": {"STATUS_FINAL", "STATUS_FULL_TIME", "FINAL"},
}
CATEGORIES = {"soccer": ("home", "draw", "away")}
BINARY_SPORTS = {"nba", "nfl", "nhl"}


def _normalized(value):
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _nhl_names():
    from nhl.pulso_goalie_multisource_257 import TEAM_NAMES
    return {code: name for code, name in TEAM_NAMES.items()}


def _forecast_chains(archive):
    root = Path(archive)
    chains, issues, sealed = [], Counter(), []
    if not root.exists():
        return chains, {"archive_missing": 1}, sealed
    for folder in sorted(root.glob("*/*")):
        if not folder.is_dir():
            continue
        paths = sorted(folder.glob("*.json"))
        if not paths:
            continue
        previous = None
        snapshots = []
        try:
            for revision, path in enumerate(paths, 1):
                snap = json.loads(path.read_text())
                verify_snapshot(snap)
                if snap.get("sport") not in SPORTS or folder.parent.name != snap["sport"]:
                    raise ValueError("sport_path_mismatch")
                events = snap.get("events")
                if not isinstance(events, list) or len(events) != 1:
                    raise ValueError("not_single_event_snapshot")
                event = events[0]
                if str(event.get("event_id", "")) == "":
                    raise ValueError("missing_event_id")
                if snap.get("revision") != revision or snap.get("parent_snapshot_sha256") != (
                    previous.get("content_sha256") if previous else None
                ):
                    raise ValueError("broken_revision_chain")
                if previous:
                    old = previous["events"][0]
                    if (previous["sport"] != snap["sport"] or
                            old.get("event_id") != event.get("event_id") or
                            old.get("participants") != event.get("participants") or
                            old.get("start_utc") != event.get("start_utc")):
                        raise ValueError("fixture_identity_changed")
                source = snap.get("source_model_output")
                source_sha = snap.get("source_output_sha256")
                if source is not None and source_sha is not None and digest(source) != source_sha:
                    raise ValueError("source_output_digest_mismatch")
                snapshots.append(snap)
                sealed.append(snap["content_sha256"])
                previous = snap
            chains.append(snapshots)
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
            issues[str(exc) or type(exc).__name__] += 1
    return chains, issues, sealed


def _history_index(history):
    if not isinstance(history, list):
        raise ValueError("History must be an array")
    index = defaultdict(list)
    for row in history:
        if not isinstance(row, dict) or row.get("sport") not in SPORTS:
            continue
        for key in {str(row.get("id", "")), str(row.get("source_event_id", ""))} - {""}:
            index[(row["sport"], key)].append(row)
    return index


def _same_start(forecast, result):
    try:
        return utc(forecast["start_utc"]) == utc(result["start_utc"])
    except (KeyError, TypeError, ValueError):
        return False


def _bind_result(sport, event, results_by_id, history):
    event_id = str(event["event_id"])
    direct = results_by_id.get((sport, event_id), [])
    candidates = [row for row in direct if _same_start(event, row)]
    if len(candidates) == 1:
        return candidates[0], None
    if len(candidates) > 1:
        return None, "ambiguous_event_id_result"

    if sport == "nhl":
        teams = _nhl_names()
        participants = event.get("participants", [])
        if len(participants) != 2:
            return None, "invalid_participants"
        home_code, away_code = participants
        home_name, away_name = teams.get(home_code), teams.get(away_code)
        if not home_name or not away_name:
            return None, "unmapped_nhl_team"
        home_key, away_key = _normalized(home_name), _normalized(away_name)
        matched = [
            row for row in history
            if row.get("sport") == sport and _same_start(event, row)
            and _normalized(row.get("home")) == home_key
            and _normalized(row.get("away")) == away_key
        ]
        if len(matched) == 1:
            return matched[0], None
        return None, "unmatched_nhl_team_and_start" if not matched else "ambiguous_nhl_team_and_start"

    if candidates:
        return candidates[0], None
    return None, "unmatched_event_id_and_start"


def _final_result(sport, row):
    if row.get("completed") is not True:
        return None, "not_completed"
    if str(row.get("status", "")).upper() not in FINAL_STATUSES[sport]:
        return None, "non_final_status"
    try:
        home, away = float(row["home_score"]), float(row["away_score"])
    except (KeyError, TypeError, ValueError):
        return None, "missing_final_score"
    if not math.isfinite(home) or not math.isfinite(away):
        return None, "invalid_final_score"
    if sport == "soccer":
        return ("home" if home > away else "away" if away > home else "draw"), None
    if sport in BINARY_SPORTS:
        if home == away:
            return None, "tied_score_not_supported_for_binary_market"
        return ("home" if home > away else "away"), None
    # Tennis score fields may represent sets, games, or live points. Until the
    # feed supplies an explicit verified match winner, do not infer the outcome.
    return None, "sport_specific_winner_not_available"


def _forecast_versions(chains):
    selected = []
    issues = Counter()
    for snapshots in chains:
        sport = snapshots[-1]["sport"]
        event = snapshots[-1]["events"][0]
        if not isinstance(event.get("forecast"), dict):
            issues["no_forecast"] += 1
            continue
        candidates = defaultdict(list)
        for snap in snapshots:
            forecast = snap["events"][0].get("forecast")
            try:
                emitted = utc(snap["emitted_at_utc"])
                start = utc(snap["events"][0]["start_utc"])
            except (KeyError, TypeError, ValueError):
                issues["invalid_emission_time"] += 1
                continue
            if snap.get("emission_kind") != "pregame" or emitted >= start:
                issues["not_pregame_emission"] += 1
                continue
            if not isinstance(forecast, dict):
                continue
            version = forecast.get("model_version")
            probs = forecast.get("probabilities")
            expected = set(CATEGORIES.get(sport, ("home", "away")))
            if not isinstance(version, str) or not version or not isinstance(probs, dict) or set(probs) != expected:
                issues["invalid_forecast_vector"] += 1
                continue
            if any(type(p) not in (int, float) or not math.isfinite(p) or p <= 0 or p >= 1 for p in probs.values()):
                issues["invalid_forecast_probability"] += 1
                continue
            if abs(sum(probs.values()) - 1) > 1e-6:
                issues["probabilities_do_not_sum_to_one"] += 1
                continue
            candidates[version].append((emitted, snap, forecast))
        for version, rows in candidates.items():
            _, snap, forecast = max(rows, key=lambda item: item[0])
            selected.append({
                "sport": sport,
                "event": snap["events"][0],
                "forecast": forecast,
                "snapshot_sha256": snap["content_sha256"],
                "emitted_at_utc": snap["emitted_at_utc"],
                "model_version": version,
                "stage": forecast["stage"],
                "model_provenance": snap.get("model_provenance"),
            })
    return selected, issues


def _score(rows, categories):
    n = len(rows)
    briers, losses, correct = [], [], 0
    for row in rows:
        probs, actual = row["probabilities"], row["outcome"]
        briers.append(sum((probs[c] - (1.0 if c == actual else 0.0)) ** 2 for c in categories) / len(categories))
        losses.append(-math.log(max(1e-15, probs[actual])))
        if max(categories, key=lambda c: probs[c]) == actual:
            correct += 1
    reliability = {}
    for category in categories:
        bins = []
        for slot in range(10):
            low, high = slot / 10, (slot + 1) / 10
            bucket = []
            for row in rows:
                p = row["probabilities"][category]
                if min(int(p * 10), 9) == slot:
                    bucket.append((p, 1.0 if row["outcome"] == category else 0.0))
            bins.append({
                "lower": low, "upper": high, "n": len(bucket),
                "forecast_mean": sum(p for p, _ in bucket) / len(bucket) if bucket else None,
                "observed_rate": sum(y for _, y in bucket) / len(bucket) if bucket else None,
            })
        reliability[category] = bins
    return {
        "n": n,
        "brier": sum(briers) / n,
        "log_loss": sum(losses) / n,
        "accuracy": correct / n,
        "reliability_bins": reliability,
    }


def evaluate(archive, history):
    """Join each version's latest pregame emission to a final result and score once."""
    results_by_id = _history_index(history)
    chains, chain_issues, sealed = _forecast_chains(archive)
    selected, forecast_issues = _forecast_versions(chains)
    exclusions = Counter(chain_issues)
    exclusions.update(forecast_issues)
    pending = 0
    scored = defaultdict(list)
    bound_forecasts = 0
    for item in selected:
        sport, event = item["sport"], item["event"]
        result, reason = _bind_result(sport, event, results_by_id, history)
        if result is None:
            exclusions[reason] += 1
            continue
        bound_forecasts += 1
        outcome, reason = _final_result(sport, result)
        if reason:
            if reason in ("not_completed", "non_final_status"):
                pending += 1
            else:
                exclusions[reason] += 1
            continue
        key = (sport, item["model_version"], item["stage"])
        scored[key].append({
            "probabilities": item["forecast"]["probabilities"],
            "outcome": outcome,
            "model_provenance": item.get("model_provenance"),
        })
    groups = []
    for (sport, version, stage), rows in sorted(scored.items()):
        provenance=[row.get("model_provenance") or {} for row in rows]
        groups.append({
            "sport": sport, "model_version": version, "stage": stage,
            "metrics": _score(rows, CATEGORIES.get(sport, ("home", "away"))),
            "lineage_coverage":{
                "scored_forecasts":len(rows),
                "with_model_code_revision":sum(bool(x.get("model_code_revision")) for x in provenance),
                "with_training_data_sha256":sum(bool(x.get("training_data_sha256")) for x in provenance),
                "with_training_cutoff_utc":sum(bool(x.get("training_cutoff_utc")) for x in provenance),
                "with_predictor_input_sha256":sum(bool(x.get("predictor_input_sha256")) for x in provenance),
                "with_predictor_input_as_of_utc":sum(bool(x.get("predictor_input_as_of_utc")) for x in provenance),
                "with_any_data_cutoff":sum(bool(x.get("training_cutoff_utc") or x.get("predictor_input_as_of_utc")) for x in provenance),
                "with_any_data_fingerprint":sum(bool(x.get("training_data_sha256") or x.get("predictor_input_sha256")) for x in provenance),
            },
        })
    return {
        "schema_version": 1,
        "kind": "sealed_forecast_outcome_evaluation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "forecast_snapshot_count": len(sealed),
            "forecast_snapshot_manifest_sha256": digest(sorted(sealed)),
            "settled_history_row_count": len(history),
            "settled_history_sha256": digest(history),
        },
        "coverage": {
            "verified_chains": len(chains),
            "latest_pregame_forecasts": len(selected),
            "forecasts_bound_to_history": bound_forecasts,
            "pending_forecasts": pending,
            "scored_forecast_groups": len(groups),
        },
        "groups": groups,
        "exclusion_counts": dict(sorted(exclusions.items())),
        "certification": {
            "certified": False,
            "independent_validation_passed": False,
            "automatic_promotion_allowed": False,
            "note": "Descriptive postgame scoring only; no independent holdout, model comparison, calibration fit, or certification is performed.",
        },
        "score_definition": "Brier is mean squared error across outcome classes; log loss uses the probability assigned to the observed outcome; reliability bins are fixed deciles.",
        "result_source_note": "Results are taken from the persisted daily history feed. Event identity is bound by provider ID and exact start, with an explicit NHL team-name crosswalk when provider IDs differ. Source authenticity is not independently attested.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", default="frontend/data/forecast_archive")
    parser.add_argument("--history", default="frontend/data/history.json")
    parser.add_argument("--output", default="frontend/data/forecast-evaluation-latest.json")
    args = parser.parse_args()
    history = json.loads(Path(args.history).read_text())
    report = evaluate(args.archive, history)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"groups": len(report["groups"]), "scored_forecast_groups": report["coverage"]["scored_forecast_groups"], "certified": False}))


if __name__ == "__main__":
    main()
