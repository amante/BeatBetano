"""Fixture-level audit of captured NHL pregame inputs and data gaps.

This is a transparency/readiness artifact. It does not calculate or promote
probabilities and never labels contextual evidence as a model feature.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from nhl.pulso_pregame_v7 import parse_utc


SUGGESTED = {
    "venue": "https://api-web.nhle.com/v1/schedule/",
    "goalie": "https://www.rotowire.com/hockey/nhl-lineups.php",
    "lines": "https://www.rotowire.com/hockey/nhl-lineups.php",
    "injuries": "https://www.rotowire.com/hockey/nhl-lineups.php",
    "player_form": "https://api-web.nhle.com/v1/player/",
    "travel_leg": "https://api-web.nhle.com/v1/club-schedule-season/",
    "rivalry": "https://api-web.nhle.com/v1/standings/",
    "special_teams": "https://api.nhle.com/stats/rest/en/team/",
    "officials": "https://api-web.nhle.com/v1/gamecenter/",
}


def read(path):
    return json.loads(Path(path).read_text()) if path else None


def read_forecasts(directory):
    if not directory:
        return {}
    records = {}
    for path in sorted(Path(directory).glob("*.json")):
        item = read(path)
        record = item.get("record", {}) if isinstance(item, dict) else {}
        if record.get("market") != "ml":
            continue
        gid = str(record.get("game_id"))
        if gid in records:
            raise ValueError("Duplicate frozen ML forecast")
        records[gid] = record
    return records


def index(rows, key="game_id"):
    if not isinstance(rows, list):
        return {}
    result = {}
    for row in rows:
        gid = str(row[key])
        if gid in result:
            raise ValueError("Duplicate game ID in source")
        result[gid] = row
    return result


def _source(url=None, captured=None):
    return {"url": url, "captured_at_utc": captured}


def _row(label, category, status, value, source=None, used=False,
         use_note="No integrado al porcentaje base publicado.", gap=None,
         suggested_source_url=None):
    return {
        "label": label,
        "category": category,
        "status": status,
        "value": value,
        "source": source or _source(),
        "used_in_base_probability": bool(used),
        "use_note": use_note,
        "gap": gap,
        "suggested_source_url": suggested_source_url if suggested_source_url is not None else SUGGESTED.get(category) if status != "captured" else None,
    }


def _identity_matches(row, fixture):
    return all(str(row.get(k)) == str(fixture.get(k)) for k in ("home", "away", "start_utc"))


def build(report, schedule, pregame, lineups, schedule_context, team_form,
          special_teams, exposure, minute_ml, publication, run_id, as_of,
          training_records=None, rotowire=None):
    if report.get("data_kind") != "source_readiness_only" or report.get("official_predictions") != 0:
        raise ValueError("Expected a source-readiness NHL report")
    now = parse_utc(as_of)
    fixtures = {str(g["game_id"]): g for g in report.get("games", [])}
    if len(fixtures) != len(report.get("games", [])):
        raise ValueError("Duplicate report fixture")
    scheduled = index(schedule.get("fixtures", [])) if schedule else {}
    pre = index(pregame.get("games", [])) if pregame else {}
    line = index(lineups.get("records", [])) if lineups else {}
    contexts = index(schedule_context.get("games", [])) if schedule_context else {}
    forms = index(team_form.get("games", [])) if team_form else {}
    absences = index(exposure.get("games", [])) if exposure else {}
    scenarios = index(minute_ml.get("games", [])) if minute_ml else {}
    published = index(publication.get("games", [])) if publication else {}
    rotowire_games = index(rotowire.get("games", [])) if rotowire else {}
    training_records = training_records or {}
    if publication and str(publication.get("run_id")) != str(run_id):
        published = {}
    team_special = special_teams.get("teams", {}) if special_teams else {}
    games = []

    for gid, fixture in fixtures.items():
        game = {"game_id": gid, "home": fixture["home"], "away": fixture["away"],
                "start_utc": fixture["start_utc"], "as_of_utc": as_of, "groups": []}
        sched = scheduled.get(gid)
        if sched and not _identity_matches({"home": sched.get("home"), "away": sched.get("away"),
                                             "start_utc": sched.get("scheduled_start")}, fixture):
            sched = None
        rows = []
        start = parse_utc(fixture["start_utc"])
        base_prediction = published.get(gid)
        if base_prediction and not _identity_matches(base_prediction, fixture): base_prediction = None
        rotowire_game = rotowire_games.get(gid)
        if rotowire_game and (not _identity_matches(rotowire_game, fixture) or
                              not rotowire_game.get("source", {}).get("captured_at_utc") or
                              parse_utc(rotowire_game["source"]["captured_at_utc"]) >= start):
            rotowire_game = None
        if sched and parse_utc(schedule.get("captured_at", "1970-01-01T00:00:00Z")) >= start:
            sched = None
        # The NHL calendar fixture is the authority for local time and venue.
        if sched:
            venue = sched.get("venue")
            rows.append(_row("Hora y recinto", "venue", "captured" if venue else "partial",
                             {"start_utc": fixture["start_utc"], "venue": venue,
                              "home_team": fixture["home"]},
                             _source(schedule.get("source_urls", [None])[0] if schedule.get("source_urls") else None,
                                     schedule.get("captured_at")),
                             gap=None if venue else "El calendario no entregó el recinto."))
        else:
            rows.append(_row("Hora y recinto", "venue", "missing",
                             {"start_utc": fixture["start_utc"], "venue": None},
                             gap="No se pudo unir el calendario oficial a este partido."))

        pregame_game = pre.get(gid)
        if pregame_game and (not _identity_matches(pregame_game, fixture) or parse_utc(pregame_game.get("feature_as_of_utc", "1970-01-01T00:00:00Z")) >= start):
            pregame_game = None
        line_game = line.get(gid)
        if line_game and (not _identity_matches(line_game, fixture) or parse_utc(line_game.get("frozen_at_utc", "1970-01-01T00:00:00Z")) >= start):
            line_game = None

        # For every side, preserve the distinction between projected and confirmed.
        sides = {}
        if pregame_game or rotowire_game:
            for team in (fixture["away"], fixture["home"]):
                side = (pregame_game or {}).get("teams", {}).get(team, {})
                proj = side.get("projected") or {}
                rw_side = (rotowire_game or {}).get("teams", {}).get(team, {})
                rw_source = (rotowire or {}).get("source", {})
                rw_players = rw_side.get("players", []) if rw_side.get("capture_status") == "captured" else []
                rw_forwards = [p for p in rw_players if p.get("position_observation") in ("C", "LW", "RW")]
                rw_defense = [p for p in rw_players if p.get("position_observation") in ("LD", "RD")]
                use_rw_roster = bool(rw_players)
                use_rw_forwards, use_rw_defense = bool(rw_forwards), bool(rw_defense)
                forwards, defense = proj.get("forwards"), proj.get("defense")
                editorial = (pregame_game or {}).get("editorial_source", {})
                source_url = rw_source.get("url") if use_rw_roster else editorial.get("url")
                source_at = rw_source.get("captured_at_utc") if use_rw_roster else (pregame_game or {}).get("feature_as_of_utc")
                goalie = rw_side.get("goalie") if rw_side.get("capture_status") == "captured" else None
                goalie_names = ([goalie.get("resolved_name") or goalie.get("name")] if goalie and goalie.get("name") else
                                [p.get("name") for p in (proj.get("goalies") or []) if p.get("name")])
                goalie_status = goalie.get("reported_status") if goalie else side.get("goalie_provider_status")
                rw_injuries = rw_side.get("injuries") or {}
                use_rw_injuries = rw_side.get("capture_status") == "captured" and rw_injuries.get("status") == "observed"
                injuries = rw_injuries.get("players") if use_rw_injuries else proj.get("injuries")
                injury_source_url = rw_source.get("url") if use_rw_injuries else editorial.get("url")
                injury_source_at = rw_source.get("captured_at_utc") if use_rw_injuries else (pregame_game or {}).get("feature_as_of_utc")
                scratches = proj.get("scratches")
                captured_at = source_at
                source_url = source_url or side.get("goalie_source")
                sides[team] = side
                if use_rw_roster:
                    captured_at, source_url = rw_source.get("captured_at_utc"), rw_source.get("url")
                attack = {"team": team, "projected_lines": forwards if not use_rw_forwards else None,
                          "players": rw_forwards if use_rw_forwards else None,
                          "source_grouping": "RotoWire lista jugadores/posiciones, no asigna trios de línea" if use_rw_forwards else "Líneas proyectadas NHL.com",
                          "complete": bool(forwards and len(forwards) == 4) if not use_rw_forwards else False}
                rows.append(_row("Delanteros / líneas de ataque", "lines",
                                 "partial" if use_rw_forwards else "captured" if forwards and len(forwards) == 4 else "partial" if forwards else "missing",
                                 attack, _source(rw_source.get("url"), rw_source.get("captured_at_utc")) if use_rw_forwards else _source(editorial.get("url"), (pregame_game or {}).get("feature_as_of_utc")),
                                 gap="RotoWire es la fuente pregame prioritaria; no publicó los trios de línea. Se muestra la lista por posición." if use_rw_forwards else None if forwards and len(forwards) == 4 else "Proyección ausente o incompleta; no equivale a alineación confirmada."))
                rows.append(_row("Pares defensivos", "lines",
                                 "partial" if use_rw_defense else "captured" if defense and len(defense) == 3 else "partial" if defense else "missing",
                                 {"team": team, "projected_pairs": defense if not use_rw_defense else None,
                                  "players": rw_defense if use_rw_defense else None,
                                  "source_grouping": "RotoWire lista defensores, no asigna pares" if use_rw_defense else "Pares defensivos NHL.com",
                                  "complete": bool(defense and len(defense) == 3) if not use_rw_defense else False},
                                 _source(rw_source.get("url"), rw_source.get("captured_at_utc")) if use_rw_defense else _source(editorial.get("url"), (pregame_game or {}).get("feature_as_of_utc")),
                                 gap="RotoWire lista defensores, pero no publica los pares." if use_rw_defense else None if defense and len(defense) == 3 else "Proyección ausente o incompleta; no equivale a alineación confirmada."))
                for pp_label, pp_key in (("Power play 1", "power_play_1"), ("Power play 2", "power_play_2")):
                    unit = rw_side.get(pp_key) or {}
                    pp_players = unit.get("players") if unit.get("status") == "observed" else None
                    rows.append(_row(pp_label, "lines", "captured" if pp_players is not None else "missing",
                                     {"team": team, "players": pp_players}, _source(source_url, captured_at),
                                     gap=None if pp_players is not None else "RotoWire no presentó esta unidad en la captura."))
                goalie_status = goalie.get("reported_status") if goalie else side.get("goalie_provider_status")
                goalie_captured = bool(goalie_names)
                goalie_confirmed = side.get("independent_starter_confirmation") is True
                rows.append(_row("Arquero y confirmación", "goalie",
                                 "captured" if goalie_captured else "missing",
                                 {"team": team, "candidatos": goalie_names, "provider_status": goalie_status,
                                  "confirmacion_independiente": goalie_confirmed,
                                  "historial": side.get("goalie_prior_statistics")},
                                 _source((rw_source.get("url") if goalie else side.get("goalie_source")),
                                         (rw_source.get("captured_at_utc") if goalie else side.get("goalie_source_captured_at"))),
                                 gap=None if goalie_confirmed else "Falta confirmar al titular con una fuente independiente.",
                                 suggested_source_url=None if goalie_confirmed else SUGGESTED["goalie"]))
                rows.append(_row("Bajas y descartados", "injuries",
                                 "captured" if injuries is not None and (scratches is not None or use_rw_injuries) else "partial" if injuries is not None or scratches is not None else "missing",
                                 {"team": team, "lesionados_reportados": injuries,
                                  "descartados_reportados": scratches},
                                 _source(injury_source_url, injury_source_at),
                                 gap=None if injuries is not None and (scratches is not None or use_rw_injuries) else "La fuente no confirmó la lista de bajas y descartados."))
        else:
            for team in (fixture["away"], fixture["home"]):
                sides[team] = {}
                for label, category in (("Delanteros / líneas de ataque", "lines"), ("Pares defensivos", "lines"),
                                        ("Power play 1", "lines"), ("Power play 2", "lines"),
                                        ("Arquero y confirmación", "goalie"), ("Bajas y descartados", "injuries")):
                    rows.append(_row(label, category, "missing", {"team": team}, gap="No se capturó evidencia pregame para el partido."))

        # Schedule and form signals are descriptive observations, not model inputs.
        game_context = contexts.get(gid)
        if game_context and (not _identity_matches(game_context, fixture) or
                             parse_utc((game_context.get("as_of_utc") or schedule_context.get("as_of_utc") or "1970-01-01T00:00:00Z")) >= start): game_context = None
        team_context_values = {}
        for team in (fixture["away"], fixture["home"]):
            context_side = (game_context or {}).get("teams", {}).get(team, {})
            team_context_values[team] = context_side
        rest_effect = (base_prediction or {}).get("module_effects", {}).get("rest", {})
        observed_context_count = sum(v.get("status") == "observed_schedule_context" for v in team_context_values.values())
        rows.append(_row("Descanso / B2B / cambio de sede", "travel_leg",
                         "captured" if observed_context_count == 2 else "partial" if observed_context_count or game_context else "missing",
                         {"teams": {t: {k: v.get(k) for k in ("status", "hours_between_starts", "rest_days_before_game", "back_to_back", "previous_venue", "venue", "venue_changed", "travel_km")} for t, v in team_context_values.items()},
                          "model_effect": rest_effect},
                         _source("https://api-web.nhle.com/v1/club-schedule-season/", (game_context or {}).get("as_of_utc")),
                         used=rest_effect.get("status") == "applied",
                         use_note="El descanso modifica Ganador solo cuando esta ejecución muestra el ajuste aplicado.",
                         gap="Secuencia de viaje, partido de ruta y retorno a casa no están capturados; solo se muestra descanso/B2B/cambio de sede disponible."))
        rows.append(_row("Tramo de gira y retorno a casa", "travel_leg", "missing", None,
                         gap="No se reconstruyó la secuencia de sedes de la gira de cada equipo."))
        rows.append(_row("Árbitros", "officials", "missing", None,
                         gap="No hay árbitros pregame capturados en este registro."))
        rows.append(_row("Rivalidad / división", "rivalry", "missing", None,
                         gap="No hay clasificador de rivalidad/división conectado a esta captura."))
        rows.append(_row("Racha reciente por jugador", "player_form", "missing", None,
                         gap="No se calculó una racha reciente individual para esta emisión."))

        historical = (line_game or {}).get("teams", {})
        individual = {}
        individual_ready = True
        for team in (fixture["away"], fixture["home"]):
            side = historical.get(team, {})
            group = side.get("groups", {}).get("projected_players", {})
            individual[team] = {"status": side.get("status"), "players_observed": group.get("observed_players", 0),
                                "players_expected": group.get("players", 0), "complete": group.get("complete", False),
                                "historical_production": group.get("observed_totals"),
                                "mean_historical_toi_minutes": group.get("mean_historical_toi_minutes")}
            individual_ready &= bool(group.get("complete"))
        rows.append(_row("Uso y producción histórica de la plantilla", "player_form",
                         "captured" if individual_ready else "partial" if any(v.get("players_observed") for v in individual.values()) else "missing",
                         individual, _source("nhl/learning/lineups/run-" + str(run_id) + ".json", (lineups or {}).get("frozen_at_utc")),
                         gap=None if individual_ready else "Faltan historiales o identidades de jugadores proyectados."))

        form_game = forms.get(gid)
        form_capture = (team_form or {}).get("source_retrieved_at_utc")
        if form_game and (not _identity_matches(form_game, fixture) or (form_capture and parse_utc(form_capture) >= start)): form_game = None
        form_sides = (form_game or {}).get("sides", {})
        observed_form = {t: form_sides.get(t, {}).get("features") for t in (fixture["away"], fixture["home"])}
        form_count = sum(v is not None for v in observed_form.values())
        rows.append(_row("Forma reciente del equipo", "player_form", "captured" if form_count == 2 else "partial" if form_count else "missing",
                         observed_form, _source((team_form or {}).get("source_url"), (team_form or {}).get("source_retrieved_at_utc")),
                         gap=None if form_count == 2 else "Falta la forma previa de uno o ambos equipos."))

        pp_pk = {t: team_special.get(t) for t in (fixture["away"], fixture["home"])}
        special_asof = (special_teams or {}).get("as_of_utc")
        if special_asof and parse_utc(special_asof) >= start:
            pp_pk = {t: None for t in (fixture["away"], fixture["home"])}
        pp_ready = all(isinstance(v, dict) and all(k in v for k in ("powerplay_goals", "powerplay_opportunities", "opponent_powerplay_goals", "times_shorthanded")) for v in pp_pk.values())
        rows.append(_row("Power play / penalty kill", "special_teams", "captured" if pp_ready else "partial" if any(pp_pk.values()) else "missing",
                         pp_pk, _source(next(iter((special_teams or {}).get("sources", [])), {}).get("url"), (special_teams or {}).get("as_of_utc")),
                         gap=None if pp_ready else "Conteos PP/PK incompletos para uno o ambos equipos."))

        exposure_game = absences.get(gid)
        if exposure_game and (not _identity_matches(exposure_game, fixture) or
                              parse_utc((exposure or {}).get("as_of_utc", "1970-01-01T00:00:00Z")) >= start): exposure_game = None
        exposure_sides = (exposure_game or {}).get("teams", {})
        lineup_effect = (base_prediction or {}).get("module_effects", {}).get("lineup_availability", {})
        replacement = {"teams": {t: exposure_sides.get(t) for t in (fixture["away"], fixture["home"])},
                       "model_effect": lineup_effect}
        replacement_ready = all(isinstance(exposure_sides.get(t), dict) and exposure_sides[t].get("status") == "conditional_replacement_scenario" for t in (fixture["away"], fixture["home"]))
        lineup_applied = lineup_effect.get("status") == "applied_experimental"
        rows.append(_row("Aportes perdidos y reemplazos", "injuries", "captured" if replacement_ready else "partial" if any(replacement.values()) else "missing",
                         replacement, _source("nhl/absence_exposure.py", (exposure or {}).get("as_of_utc")),
                         used=lineup_applied,
                         use_note="La disponibilidad cambió ML en esta emisión mediante escenario experimental." if lineup_applied else "Hay exposición capturada, pero no modificó el porcentaje en esta emisión.",
                         gap=None if replacement_ready else "La redistribución no puede calcularse con los historiales o minutos disponibles."))

        scenario = scenarios.get(gid)
        if scenario and (not _identity_matches(scenario, fixture) or
                         parse_utc((minute_ml or {}).get("as_of_utc", "1970-01-01T00:00:00Z")) >= start): scenario = None
        scenario_present = scenario and scenario.get("status") == "experimental_minute_scenario"
        rows.append(_row("Goles y ML con reemplazos (escenario)", "injuries",
                         "captured" if scenario_present else "blocked" if scenario and scenario.get("status") == "blocked" else "missing",
                         scenario, _source("nhl/minute_adjusted_ml.py", (minute_ml or {}).get("as_of_utc")),
                         used=False, use_note="Escenario auxiliar; revisa el efecto de disponibilidad para ver si se aplicó a ML.",
                         gap=None if scenario_present else (scenario or {}).get("reason") or "No hay escenario de goles con reemplazos para este partido."))

        rows.append(_row("Porcentaje base publicado", "forecast", "captured" if base_prediction and base_prediction.get("status") == "experimental_forecast" else "missing",
                         {"status": (base_prediction or {}).get("status"), "model": (base_prediction or {}).get("model"),
                          "ml": (base_prediction or {}).get("ml")},
                         _source("frontend/data/nhl-daily-predictions-latest.json", None),
                         used=False, use_note="Resultado experimental; los efectos conectados se muestran en los módulos que esta corrida marca como aplicados.",
                         gap=None if base_prediction else "No se publicó un porcentaje base para este partido."))
        training = training_records.get(gid)
        if training and (training.get("home") != fixture["home"] or training.get("away") != fixture["away"] or
                         training.get("start_utc") != fixture["start_utc"] or
                         parse_utc(training.get("prediction_as_of_utc", "1970-01-01T00:00:00Z")) >= start):
            training = None
        training_ok = bool(training and isinstance(training.get("historical_prior_date_games"), int) and
                           isinstance(training.get("historical_labels_sha256"), str) and len(training["historical_labels_sha256"]) == 64)
        rows.append(_row("Historial previo usado por el baseline", "forecast", "captured" if training_ok else "missing",
                         {"modelo": (training or {}).get("model_version"),
                          "juegos_historicos_previos": (training or {}).get("historical_prior_date_games"),
                          "fecha_emision": (training or {}).get("prediction_as_of_utc")},
                         _source((training or {}).get("source_url"), (training or {}).get("prediction_as_of_utc")),
                         used=training_ok,
                         use_note="Aporta la base histórica; los ajustes pregame aplicados aparecen por separado en las filas de disponibilidad y descanso.",
                         gap=None if training_ok else "No se pudo vincular el registro congelado de entrenamiento."))

        game["groups"] = [
            {"title": "Partido", "rows": [r for r in rows if r["category"] == "venue"]},
            {"title": "Alineaciones y portería", "rows": [r for r in rows if r["label"] in ("Delanteros / líneas de ataque", "Líneas de ataque", "Pares defensivos", "Power play 1", "Power play 2", "Arquero y confirmación")]},
            {"title": "Disponibilidad y reemplazos", "rows": [r for r in rows if r["label"] in ("Bajas y descartados", "Aportes perdidos y reemplazos", "Goles y ML con reemplazos (escenario)")]},
            {"title": "Ritmo, viaje y forma", "rows": [r for r in rows if r["label"] in ("Descanso / B2B / cambio de sede", "Tramo de gira y retorno a casa", "Rivalidad / división", "Racha reciente por jugador", "Forma reciente del equipo", "Uso y producción histórica de la plantilla")]},
            {"title": "Árbitros", "rows": [r for r in rows if r["label"] == "Árbitros"]},
            {"title": "Equipos especiales y pronóstico", "rows": [r for r in rows if r["label"] in ("Power play / penalty kill", "Porcentaje base publicado", "Historial previo usado por el baseline")]},
        ]
        game["missing_count"] = sum(r["status"] in ("missing", "partial", "blocked") for r in rows)
        game["captured_count"] = sum(r["status"] == "captured" for r in rows)
        game["input_rows"] = len(rows)
        games.append(game)

    return {"kind": "nhl_pregame_input_inventory_v1", "run_id": str(run_id),
            "as_of_utc": as_of, "date": report.get("date"), "games": games,
            "probabilities_modified": False,
            "limitations": [
                "La ficha audita las capturas; no ajusta ni certifica el modelo.",
                "Solo se marca como influyente el módulo que la predicción registra explícitamente como aplicado.",
                "Los enlaces sugeridos son fuentes para consultar, no evidencia de que la página haya respondido.",
                "Al buscar un faltante se inicia una corrida nueva; la captura histórica queda preservada.",
            ]}


def main():
    parser = argparse.ArgumentParser()
    for arg in ("report", "schedule", "pregame", "lineups", "schedule-context", "team-form",
                "special-teams", "exposure", "minute-ml", "publication", "forecast-dir", "rotowire", "output", "run-id"):
        parser.add_argument("--" + arg, required=arg in ("report", "schedule", "pregame", "lineups", "schedule-context", "team-form", "special-teams", "exposure", "minute-ml", "publication", "forecast-dir", "rotowire", "output", "run-id"))
    args = parser.parse_args()
    inputs = {name.replace("-", "_"): read(getattr(args, name.replace("-", "_"))) for name in
              ("report", "schedule", "pregame", "lineups", "schedule_context", "team_form", "special_teams", "exposure", "minute_ml", "publication")}
    result = build(**inputs, run_id=args.run_id, as_of=datetime.now(timezone.utc).isoformat(), training_records=read_forecasts(args.forecast_dir), rotowire=read(args.rotowire))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"games": len(result["games"]), "missing_or_partial": sum(g["missing_count"] for g in result["games"]), "captured": sum(g["captured_count"] for g in result["games"]), "probabilities_modified": False}))


if __name__ == "__main__":
    main()
