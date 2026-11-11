"""Fail-closed readiness gate for independent model certification review.

Passing this gate only means an evidence packet is ready for human review. It
never certifies, calibrates, selects, or promotes a production model.
"""
import re
from datetime import datetime, timezone

from multisport.walk_forward import evaluate as evaluate_walk_forward

HEX_64 = re.compile(r"^[0-9a-f]{64}$")
HEX_REVISION = re.compile(r"^[0-9a-f]{7,40}$")
REVIEW_CHECKS = (
    "source_authenticity_verified",
    "lineage_verified",
    "temporal_leakage_reviewed",
    "reliability_reviewed",
)


def _utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("UTC timestamp required")
    return parsed


def _sha(value, label):
    if not isinstance(value, str) or not HEX_64.fullmatch(value):
        raise ValueError(label + " must be a lowercase SHA-256 digest")


def assess(evidence):
    """Assess a frozen holdout packet; return reasons and never set certified=True."""
    if not isinstance(evidence, dict):
        raise ValueError("Evidence packet must be an object")
    scope = evidence.get("scope")
    if not isinstance(scope, dict) or any(
        not isinstance(scope.get(key), str) or not scope[key].strip()
        for key in ("sport", "market", "model_version")
    ):
        raise ValueError("Sport, market, and model version are required")

    protocol = evidence.get("protocol")
    if not isinstance(protocol, dict):
        raise ValueError("A frozen holdout protocol is required")
    seasons = protocol.get("holdout_seasons")
    if not isinstance(seasons, list) or len(seasons) < 2 or len(set(seasons)) != len(seasons):
        raise ValueError("At least two distinct holdout seasons are required")
    minimum = protocol.get("min_games_per_season")
    if type(minimum) is not int or minimum < 100:
        raise ValueError("Minimum 100 games per holdout season is required")
    locked_at = _utc(protocol["locked_at_utc"])
    first_prediction = _utc(protocol["first_holdout_prediction_utc"])
    if locked_at >= first_prediction:
        raise ValueError("Holdout protocol must be locked before its first prediction")
    ablations = protocol.get("required_ablations")
    if not isinstance(ablations, list) or not ablations or any(
        not isinstance(name, str) or not name.strip() for name in ablations
    ):
        raise ValueError("At least one predeclared ablation is required")

    lineage = evidence.get("lineage")
    if not isinstance(lineage, dict):
        raise ValueError("Model and data lineage is required")
    _sha(lineage.get("forecast_archive_sha256"), "forecast_archive_sha256")
    _sha(lineage.get("training_data_manifest_sha256"), "training_data_manifest_sha256")
    if not isinstance(lineage.get("model_code_revision"), str) or not HEX_REVISION.fullmatch(lineage["model_code_revision"]):
        raise ValueError("A Git model-code revision is required")

    rows = evidence.get("walk_forward_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Walk-forward holdout rows are required")
    if any(row.get("season") not in seasons for row in rows):
        raise ValueError("Evaluation rows include seasons outside the frozen holdout")
    earliest = min(_utc(row["prediction_as_of_utc"]) for row in rows)
    if locked_at >= earliest:
        raise ValueError("Holdout protocol was not frozen before the supplied predictions")
    screening = evaluate_walk_forward(
        rows,
        seasons,
        min_games=minimum,
        required_ablations=ablations,
    )

    review = evidence.get("independent_review")
    review_complete = isinstance(review, dict) and all(
        review.get(check) is True for check in REVIEW_CHECKS
    )
    if review_complete:
        review_complete = (
            isinstance(review.get("reviewer_id"), str) and bool(review["reviewer_id"].strip())
            and isinstance(review.get("evidence_ref"), str) and bool(review["evidence_ref"].strip())
            and _utc(review["reviewed_at_utc"]) >= earliest
        )

    reasons = list(screening["reasons"])
    if not review_complete:
        reasons.append("independent_review_incomplete")
    ready = not reasons
    return {
        "schema_version": 1,
        "scope": dict(scope),
        "holdout": {
            "seasons": seasons,
            "min_games_per_season": minimum,
            "protocol_locked_before_holdout": True,
            "screening_passed": screening["screening_passed"],
            "by_season": screening["by_season"],
        },
        "lineage_present": True,
        "independent_review_complete": review_complete,
        "eligible_for_certification_review": ready,
        "certified": False,
        "automatic_promotion_allowed": False,
        "reasons": reasons,
        "note": "Eligibility is not certification. A human reviewer must inspect the referenced evidence; this gate does not authenticate attestations or promote models.",
    }
