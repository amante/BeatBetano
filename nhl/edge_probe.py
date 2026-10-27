"""Minimal manual NHL EDGE availability probe; no bulk requests or model promotions."""
import argparse
import json
import time
from pathlib import Path
import requests

ROOT = "https://api-web.nhle.com/v1/edge"
STATS = "https://api.nhle.com/stats/rest/en"
ENDPOINTS = {
    "team_detail": "/team-detail/9/20252026/2",
    "skater_detail": "/skater-detail/8482116/20252026/2",
    "goalie_detail": "/goalie-detail/8476945/20252026/2",
    "core_skater_summary": STATS + "/skater/summary?cayenneExp=seasonId=20252026&limit=2",
    "core_goalie_summary": STATS + "/goalie/summary?cayenneExp=seasonId=20252026&limit=2",
    "core_team_summary": STATS + "/team/summary?cayenneExp=seasonId=20252026&limit=2",
}

def run(fetch, pause=lambda: None):
    rows = []
    for name, path in ENDPOINTS.items():
        try:
            url = path if path.startswith("https://") else ROOT + path
            r = fetch(url)
            status = r.status_code
            result = {"endpoint": name, "http_status": status,
                      "url_path": url.split("?")[0], "json_ok": False, "top_level_keys": [], "records": 0}
            if status == 200:
                try:
                    payload = r.json()
                    result["json_ok"] = isinstance(payload, dict) and bool(payload)
                    if isinstance(payload, dict):
                        result["top_level_keys"] = sorted(payload.keys())[:30]
                        if isinstance(payload.get("data"),list):
                            result["records"] = len(payload["data"])
                except ValueError:
                    pass
            if status == 429:
                result["retry_after"] = r.headers.get("Retry-After")
            rows.append(result)
        except requests.RequestException as e:
            rows.append({"endpoint": name, "http_status": None,
                         "url_path": path, "json_ok": False,
                         "error": type(e).__name__})
        pause()
    return {"source": "NHL Stats REST and NHL EDGE", "purpose": "non-calibrated availability check",
            "endpoint_results": rows, "usable": any(x["json_ok"] for x in rows)}

def markdown(data):
    lines = ["## NHL Core Stats + EDGE — direct endpoint check", "",
             "Small, manual, rate-limited probe. No sports ratings or betting probabilities are produced.",
             "", "| Endpoint | HTTP | JSON | Response fields |",
             "|---|---:|---|---|"]
    for x in data["endpoint_results"]:
        lines.append("| {} | {} | {} | {} |".format(
            x["endpoint"], x["http_status"] if x["http_status"] is not None else "error",
            "yes" if x["json_ok"] else "no", ", ".join(x.get("top_level_keys", [])[:8]) or "—"))
    lines += ["", "**Usable EDGE endpoint:** " + ("Yes" if data["usable"] else "No"),
              "", "A 429 means rate-limited; do not retry in a tight loop."]
    return "\n".join(lines) + "\n"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--summary", required=True)
    args = p.parse_args()
    # Explicitly slow down requests; never attempt bulk collection here.
    session = requests.Session()
    data = run(lambda url: session.get(url, timeout=20), lambda: time.sleep(2))
    for path, content in ((args.output, json.dumps(data, indent=2)),
                          (args.summary, markdown(data))):
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
    print(json.dumps({"usable": data["usable"],
                      "statuses": [r["http_status"] for r in data["endpoint_results"]]}))
    if not data["usable"]:
        raise SystemExit("No NHL EDGE data retrieved; see Actions Summary")

if __name__ == "__main__":
    main()
