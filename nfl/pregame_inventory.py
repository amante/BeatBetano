"""Per-game NFL input audit consumed by the shared PULSO forecast card.

This is descriptive evidence only; it never adjusts model percentages.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def utc(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return dt.astimezone(timezone.utc)


def index(rows, name):
    result = {}
    for row in rows or []:
        key = str(row["event_id"])
        if key in result:
            raise ValueError("Duplicate event in " + name)
        result[key] = row
    return result


def item(label, status, value=None, source=None, used=False, note="", gap=None):
    return {
        "label": label,
        "status": status,
        "value": value,
        "source": source or {},
        "used_in_base_probability": bool(used),
        "use_note": note,
        "gap": gap,
    }


def build(slate, evidence, reconciled, run_id, generated_at=None):
    if any(x.get("sport") != "nfl" for x in (slate, evidence, reconciled)):
        raise ValueError("NFL inputs required")
    as_of = utc(slate["as_of_utc"])
    obs = index(evidence.get("games", []), "evidence")
    verified = index(reconciled.get("games", []), "reconciliation")
    games = []
    seen = set()
    for fixture in slate.get("events", []):
        gid = str(fixture["event_id"])
        if gid in seen:
            raise ValueError("Duplicate fixture")
        seen.add(gid)
        kickoff = utc(fixture["start_utc"])
        if as_of >= kickoff:
            raise ValueError("Capture must precede kickoff")
        report = obs.get(gid, {})
        resolved = verified.get(gid, {})
        report_time = report.get("observed_at_utc")
        observed_after_emission = bool(report_time and utc(report_time) > as_of)
        source = {
            "provider": "ESPN",
            "url": report.get("source"),
            "captured_at_utc": report_time,
            "available_after_forecast_cutoff": observed_after_emission,
        }
        timing_note = (
            "Captura posterior al corte del pronóstico inicial; aporta contexto, "
            "pero no formó parte de ese porcentaje."
            if observed_after_emission
            else ""
        )
        listed = []
        for group in report.get("injury_observations", []):
            for player in group.get("observations", []):
                listed.append(
                    {
                        "team": group.get("team"),
                        "name": player.get("name"),
                        "position": player.get("position"),
                        "status": player.get("status"),
                        "confirmed_inactive": False,
                    }
                )
        qbs = [p for p in listed if p.get("position") == "QB"]
        inactive = [
            {
                "team": p.get("team"),
                "id": p.get("player_id"),
                "position": p.get("position"),
                "status": "INACTIVE",
                "confirmed_inactive": True,
                "source": p.get("source_url"),
            }
            for p in resolved.get("verified_players", [])
            if p.get("official_inactive_confirmed") is True
        ]
        p = fixture.get("historical_elo_candidate")
        groups = [
            {
                "title": "Partido y sede",
                "rows": [
                    item("Inicio", "captured", fixture["start_utc"], source),
                    item(
                        "Estadio",
                        "captured" if fixture.get("venue") else "missing",
                        {
                            "stadium": fixture.get("venue"),
                            "city": fixture.get("city"),
                            "neutral_site": fixture.get("neutral_site", False),
                        },
                        source,
                        gap=None if fixture.get("venue") else "El marcador no entregó el estadio.",
                    ),
                ],
            },
            {
                "title": "Probabilidad base",
                "rows": [
                    item(
                        "Elo histórico",
                        "captured" if isinstance(p, (int, float)) else "missing",
                        {
                            "model": "nfl-historical-elo",
                            "home": fixture.get("home_name", fixture["home_team"]),
                            "away": fixture.get("away_name", fixture["away_team"]),
                            "home_probability": p,
                            "away_probability": 1 - p if isinstance(p, (int, float)) else None,
                            "historical_games": slate.get("historical_games_used"),
                            "training_cutoff_utc": slate.get("model_provenance", {}).get(
                                "training_cutoff_utc"
                            ),
                        },
                        {
                            "provider": "nflverse historical results",
                            "captured_at_utc": slate["as_of_utc"],
                        },
                        True,
                        "Único factor que determina este porcentaje candidato; Elo exploratorio, sin calibración certificada.",
                    ),
                    item(
                        "Corte del pronóstico inicial",
                        "captured",
                        slate["as_of_utc"],
                        {"captured_at_utc": slate["as_of_utc"]},
                        False,
                        "Los datos capturados después de este momento no alteraron la emisión inicial.",
                    ),
                ],
            },
            {
                "title": "QB, lesiones e inactivos",
                "rows": [
                    item(
                        "QB",
                        "partial" if qbs else "missing",
                        {
                            "reportados": qbs,
                            "titular_confirmado": report.get("starting_qbs_verified") is True,
                        },
                        source if report else {},
                        note=timing_note,
                        gap="El reporte no confirma el QB titular ni su disponibilidad oficial.",
                    ),
                    item(
                        "Inactivos oficiales",
                        "captured" if inactive else "missing",
                        inactive,
                        {"captured_at_utc": as_of.isoformat()} if inactive else {},
                        gap=None if inactive else "No hay inactivos oficiales reconciliados para el partido.",
                    ),
                    item(
                        "Lesiones del proveedor",
                        "partial" if listed else "missing",
                        listed,
                        source if listed else {},
                        note=(
                            "Observación auxiliar; no se trata como baja confirmada ni cambia el porcentaje."
                            + (" " + timing_note if timing_note else "")
                        ),
                        gap="Sin fuente en esta captura." if not listed else None,
                    ),
                ],
            },
            {
                "title": "Matchups y condiciones",
                "rows": [
                    item("Línea ofensiva y reemplazos", "missing", gap="No hay titulares, roles y reemplazos reconciliados."),
                    item("Defensa rival y cobertura", "missing", gap="No hay asignaciones de matchup verificadas."),
                    item(
                        "Clima",
                        "captured" if resolved.get("weather_forecast") else "missing",
                        resolved.get("weather_forecast"),
                        gap=None if resolved.get("weather_forecast") else "Sin pronóstico pregame conectado al cálculo.",
                    ),
                    item("Descanso y viaje", "missing", gap="Sin descanso, viaje ni zona horaria capturados."),
                    item("EPA challenger", "missing", gap="EPA se evalúa en histórico; aún no alimenta la corrida."),
                    item("Props individuales", "missing", gap="No hay modelo de props validado; las cuotas no entran al modelo."),
                ],
            },
        ]
        games.append(
            {
                "event_id": gid,
                "start_utc": fixture["start_utc"],
                "home": fixture["home_team"],
                "away": fixture["away_team"],
                "home_name": fixture.get("home_name", fixture["home_team"]),
                "away_name": fixture.get("away_name", fixture["away_team"]),
                "forecast_cutoff_utc": slate["as_of_utc"],
                "supplement_captured_after_forecast_cutoff": observed_after_emission,
                "groups": groups,
            }
        )
    return {
        "kind": "nfl_pregame_input_inventory_v1",
        "sport": "nfl",
        "run_id": str(run_id),
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "as_of_utc": slate["as_of_utc"],
        "official_prediction": False,
        "odds_used_in_model": False,
        "games": games,
        "note": "Evidencia y faltantes por encuentro; los campos pendientes no modifican los porcentajes.",
    }


def main():
    parser = argparse.ArgumentParser()
    for key in ("slate", "evidence", "reconciled", "run-id", "output"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    load = lambda p: json.loads(Path(p).read_text())
    data = build(load(args.slate), load(args.evidence), load(args.reconciled), args.run_id)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    print(
        json.dumps(
            {
                "games": len(data["games"]),
                "run_id": data["run_id"],
                "official_prediction": False,
                "late_evidence_games": sum(
                    g["supplement_captured_after_forecast_cutoff"] for g in data["games"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
