"""Cross-sport model registry and reproducibility gate; no model is auto-promoted."""
import hashlib,json
from datetime import datetime,timezone

SPORTS=("nba","nfl","nhl","soccer","tennis")
REQUIRED=("sport","model_name","version","feature_cutoff_utc","training_cutoff_utc",
          "dataset_sha256","code_revision","calibration_report","validation_state")
STATES=("research","candidate","independently_validated","retired")

def moment(value):
    dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if dt.tzinfo is None:raise ValueError("Timezone required")
    return dt.astimezone(timezone.utc)

def fingerprint(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def validate_record(record):
    missing=[k for k in REQUIRED if k not in record]
    if missing:raise ValueError("Missing model metadata: "+",".join(missing))
    if record["sport"] not in SPORTS:raise ValueError("Unknown sport")
    if record["validation_state"] not in STATES:raise ValueError("Invalid validation state")
    if not all(isinstance(record[k],str) and record[k].strip() for k in ("model_name","version","code_revision")):
        raise ValueError("Model name/version/revision required")
    digest=record["dataset_sha256"]
    if not isinstance(digest,str) or len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Dataset SHA256 required")
    if moment(record["training_cutoff_utc"])>moment(record["feature_cutoff_utc"]):
        raise ValueError("Training after features: leakage")
    if record["validation_state"]=="independently_validated":
        report=record["calibration_report"]
        if not isinstance(report,dict) or not all(report.get(x) for x in ("report_ref","holdout_seasons","independent_review_passed")):
            raise ValueError("Independent validation evidence required")
        if len(report["holdout_seasons"])<2:raise ValueError("Two holdout seasons required")
    return True

def registry_report(records):
    if not isinstance(records,list):raise ValueError("Registry must be list")
    seen=set();report=[]
    for x in records:
        validate_record(x)
        key=(x["sport"],x["model_name"],x["version"])
        if key in seen:raise ValueError("Duplicate version")
        seen.add(key)
        report.append({"sport":x["sport"],"name":x["model_name"],"version":x["version"],
          "state":x["validation_state"],"fingerprint":fingerprint(x),
          "release_eligible":x["validation_state"]=="independently_validated"})
    return {"entries":report,"automatic_promotion":False,
      "note":"Registry certification flags are attestations, not proof without independent source review."}
