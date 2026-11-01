"""PULSO #260: capture point-in-time NHL game logs for EVERY #258 goalie candidate.

External roster candidates are not automatically starters. Sources remain
descriptive; this module neither fits probabilities nor substitutes GSAx.
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from nhl.pulso_goalie_history_251 import fetch, metrics, season_for
from nhl.pulso_pregame_v7 import parse_utc

def collect(scenarios, report, fetcher=fetch):
    if scenarios.get("kind") != "nhl_goalie_conditional_scenarios_258":
        raise ValueError("Wrong scenario evidence")
    if report.get("data_kind") != "source_readiness_only":
        raise ValueError("Wrong report evidence")
    asof = parse_utc(report["generated_at_utc"])
    if parse_utc(scenarios["as_of_utc"]) != asof:
        raise ValueError("Capture timestamp mismatch")
    fixture_index = {str(f["game_id"]): f for f in report["games"]}
    if len(fixture_index) != len(report["games"]):
        raise ValueError("Duplicate fixture")
    requests = {}
    for game in scenarios["games"]:
        gid = str(game["game_id"])
        fixture = fixture_index.get(gid)
        if fixture is None or (fixture["home"], fixture["away"]) != (game["home"], game["away"]):
            raise ValueError("Fixture mismatch")
        start = parse_utc(fixture["start_utc"])
        if start <= asof:
            raise ValueError("Not a pregame fixture")
        for team in (game["home"], game["away"]):
            for candidate in game["goalie_candidates"][team]:
                pid = candidate["player_id"]
                if type(pid) is not int or pid <= 0:
                    raise ValueError("Invalid candidate goalie ID")
                requests.setdefault(pid, set()).add(gid)
    season = season_for(asof.date().isoformat())
    fetched = {}
    def retrieve(pid):
        try:
            return pid, fetcher(pid, season), None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return pid, None, type(exc).__name__
    with ThreadPoolExecutor(max_workers=5) as pool:
        for task in as_completed([pool.submit(retrieve, pid) for pid in sorted(requests)]):
            pid, response, error = task.result()
            fetched[pid] = (response, error)
    games = []
    observed = 0
    for game in scenarios["games"]:
        gid = str(game["game_id"])
        fixture = fixture_index[gid]
        start = parse_utc(fixture["start_utc"])
        teams = {}
        for team in (game["home"], game["away"]):
            candidates = []
            for candidate in game["goalie_candidates"][team]:
                pid = candidate["player_id"]
                response, error = fetched[pid]
                entry = {"player_id": pid, "name": candidate["name"],
                         "candidate_source": candidate["source"],
                         "candidate_status": candidate["status"],
                         "independently_confirmed_starter": False,
                         "official_ml_impact": None}
                if error:
                    entry.update(status="blocked", reason="fetch_" + error)
                else:
                    payload, meta = response
                    try:
                        retrieved = parse_utc(meta["retrieved_at"])
                        if not (asof <= retrieved < start):
                            entry.update(status="blocked", reason="outside_fixture_pregame_window")
                        else:
                            summary = metrics(payload, asof.date().isoformat())
                            entry.update(status="observed" if summary["season_to_date"]["games"] else "no_prior_games",
                                         metrics=summary, source=meta)
                            observed += entry["status"] == "observed"
                    except (KeyError, TypeError, ValueError) as exc:
                        entry.update(status="blocked", reason="malformed_history_" + type(exc).__name__)
                candidates.append(entry)
            teams[team] = candidates
        games.append({"game_id": gid, "home": game["home"], "away": game["away"], "teams": teams})
    if len(games) != len(fixture_index):
        raise ValueError("Incomplete fixture coverage")
    return {"kind": "nhl_all_goalie_candidates_history_260", "as_of_utc": report["generated_at_utc"],
            "season": season, "games": games, "distinct_candidate_ids": len(requests),
            "candidate_fixture_sides": sum(len(v) for g in games for v in g["teams"].values()),
            "observed_candidates": observed, "official_predictions": 0,
            "odds_used": False, "calibrated": False,
            "note": "Every scenario candidate gets a dated observation or an explicit blocker; not starter confirmation or fitted probabilities."}

def main():
    parser = argparse.ArgumentParser()
    for key in ("scenarios", "report", "out"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    result = collect(json.loads(Path(args.scenarios).read_text()),
                     json.loads(Path(args.report).read_text()))
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in ("distinct_candidate_ids", "candidate_fixture_sides",
                                           "observed_candidates", "official_predictions")}))
if __name__ == "__main__":
    main()
