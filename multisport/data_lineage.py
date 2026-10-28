"""Validate point-in-time source lineage independently of sport-specific models."""
import hashlib,json
from datetime import datetime,timezone

def utc(value):
    x=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if x.tzinfo is None:raise ValueError("Timezone required")
    return x.astimezone(timezone.utc)

def verify_manifest(manifest):
    if not isinstance(manifest,dict):raise ValueError("Manifest must be an object")
    freeze=utc(manifest["prediction_as_of_utc"])
    start=utc(manifest["event_start_utc"])
    if freeze>=start:raise ValueError("Not pregame")
    entries=manifest.get("sources")
    if not isinstance(entries,list) or not entries:raise ValueError("Source evidence is required")
    observed=[]
    for s in entries:
        if not all(isinstance(s.get(k),str) and s[k].strip() for k in ("source_id","observed_at_utc","content_sha256")):
            raise ValueError("Incomplete source provenance")
        sha=s["content_sha256"]
        if len(sha)!=64 or any(ch not in "0123456789abcdef" for ch in sha):
            raise ValueError("Invalid source sha256")
        when=utc(s["observed_at_utc"])
        if when>freeze:raise ValueError("Future source observation")
        observed.append(when)
    if manifest.get("odds_used_in_model") is not False:raise ValueError("Market odds prohibited")
    return {"source_count":len(entries),"latest_observation_utc":max(observed).isoformat(),
        "pregame":True,"point_in_time_checks_passed":True,
        "independent_source_authenticity_verified":False}

def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()
