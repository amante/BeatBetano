"""One auditable daily NBA slate; no invented final probabilities or partial slates."""
import argparse
import json
import math
from pathlib import Path


def assemble(snapshot, integrated, injury_lineups=None, postmortem=None):
    injury_lineups = injury_lineups or {}
    if integrated.get("statistical_snapshot_sha256") != snapshot.get("content_sha256"):
        raise ValueError("Integrated results do not match statistical snapshot")
    fixtures = {str(p["game_id"]): p for p in snapshot["predictions"]}
    if len(fixtures) != len(snapshot["predictions"]) or not fixtures:
        raise ValueError("Empty or duplicate fixture IDs")
    rows = integrated.get("predictions", [])
    matched = {str(p["game_id"]): p for p in rows}
    if len(matched) != len(rows) or set(matched) != set(fixtures):
        raise ValueError("Integrated game IDs do not cover full slate exactly")
    intake = injury_lineups.get("games", {})
    if not isinstance(intake, dict):
        raise ValueError("Injury/lineup mapping invalid")
    games = []
    research = {}
    if postmortem is not None:
        from postmortem_engine import verify_seal, VERSION
        verify_seal(postmortem)
        if postmortem.get("model_version") != VERSION:
            raise ValueError("Unsupported postmortem model version")
        if postmortem.get("baseline_snapshot_sha256") != snapshot.get("content_sha256"):
            raise ValueError("Postmortem report / baseline mismatch")
        research = {str(g["game_id"]): g for g in postmortem["games"]}
        if len(research) != len(postmortem["games"]) or set(research) != set(fixtures):
            raise ValueError("Postmortem report must cover the complete slate")
    for gid, p in fixtures.items():
        row = matched[gid]
        if (p["home_team"], p["away_team"]) != (row["home_team"], row["away_team"]):
            raise ValueError("Team mismatch for game " + gid)
        status = intake.get(gid, {})
        final = row.get("integrated_p_home")
        approved = (
            type(final) in (int, float) and math.isfinite(final)
            and 0 < final < 1
            and row.get("all_sporting_steps_verified") is True
            and row.get("impact_model_independently_validated") is True
            and row.get("status") == "integrated_candidate"
        )
        if final is not None and not approved:
            raise ValueError("Unapproved numerical final for game " + gid)
        # The post-mortem gate is mandatory for both teams, ML and +20. This
        # research estimator cannot authorize production, even with full inputs.
        gate = research.get(gid)
        if gate and (gate["home_team"],gate["away_team"],gate["tipoff_utc"]) != (p["home_team"],p["away_team"],p["tipoff_utc"]):
            raise ValueError("Postmortem fixture identity mismatch")
        gate_reasons = gate.get("missing", []) if gate else ["Missing two-sided replacement and score-path evaluation"]
        home = None
        games.append({
            "game_id": gid, "tipoff_utc": p["tipoff_utc"],
            "home_team": p["home_team"], "away_team": p["away_team"],
            "official_baseline_p_home": row.get("elo_p_home"),
            "challenger_baseline_p_home": row.get("challenger_p_home"),
            "hybrid_baseline_p_home": row.get("hybrid_p_home"),
            "hybrid_route": p.get("hybrid_route","unknown"),
            "legacy_integrated_diagnostic_p_home": final if approved else None,
            "final_p_home": home,
            "final_p_away": None,
            "final_status": "PASS_pending_postmortem_validation",
            "recommendation": "PASS",
            "eligible_for_bet": False,
            "home_reach_plus20": None, "away_reach_plus20": None,
            "postmortem_gate_reasons": gate_reasons,
            "postmortem_research": gate,
            "starting_fives_confirmed": status.get("lineups_confirmed") is True,
            "official_injuries_resolved": status.get("official_player_team_status_confirmed") is True,
            "missing_evidence": [k for k, v in row.get("evidence_checks", {}).items() if v is not True],
            "sporting_observations": row.get("sporting_observations", {}),
        })
    games.sort(key=lambda x: (x["tipoff_utc"], x["game_id"]))
    return {
        "schema_version": 1, "command": "NBA hoy",
        "snapshot_sha256": snapshot["content_sha256"],
        "games_expected": len(fixtures), "games_returned": len(games),
        "complete_slate": len(games) == len(fixtures),
        "all_final_probabilities_available": all(g["final_p_home"] is not None for g in games),
        "no_odds_input": True,
        "games": games
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--integrated", required=True)
    parser.add_argument("--injury-lineups")
    parser.add_argument("--postmortem")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    load = lambda p: json.loads(Path(p).read_text()) if p else {}
    result = assemble(load(args.snapshot), load(args.integrated), load(args.injury_lineups),
                      load(args.postmortem) if args.postmortem else None)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2))
    print(json.dumps({"games": result["games_returned"],
                      "final_probabilities": sum(g["final_p_home"] is not None for g in result["games"])}))


if __name__ == "__main__":
    main()
