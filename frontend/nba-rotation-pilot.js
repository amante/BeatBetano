"use strict";
(async function () {
  if (new URLSearchParams(location.search).get("sport") !== "nba") return;
  const root = document.getElementById("nba-rotation-pilot");
  if (!root) return;

  const formatTime = new Intl.DateTimeFormat("es-CL", {
    timeZone: "America/Santiago", dateStyle: "medium", timeStyle: "short"
  });
  const formatPct = new Intl.NumberFormat("es-CL", { style: "percent", maximumFractionDigits: 2 });
  const labels = {
    incomplete_usage_sample: "Muestra de carga ofensiva incompleta",
    unsupported_player_effect: "Efectos individuales insuficientes",
    PASS_insufficient_path_sample: "Muestra de trayectorias insuficiente",
    PASS_opponent_context_missing: "Muestra de rivales insuficiente",
    insufficient_opponent_adjusted_ratings: "Eficiencia ajustada por rival insuficiente",
    missing_path_features: "Sin datos de trayectorias",
    missing_minute_allocation: "Rotación sin minutos estimados",
    already_started: "Partido ya iniciado al momento de la corrida",
    rotation_inputs_unavailable: "Faltan fuentes para el escenario de rotación",
    baseline_input_unavailable: "No se pudo construir la emisión base para este partido",
    missing_rotation_scenario: "Escenario de rotación ausente",
    no_reliable_minute_history: "Falta una muestra histórica fiable de minutos",
    out_player_missing_minute_estimate: "No hay dos apariciones históricas para estimar los minutos de una baja",
    minute_allocation_infeasible: "No se pueden distribuir los 240 minutos con estos límites"
  };
  const el = (tag, value, className) => {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const time = value => Date.parse(value);
  const probability = value => typeof value === "number" && value >= 0 && value <= 1;
  const number = (value, digits = 1) => typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("es-CL", { maximumFractionDigits: digits }).format(value) : "—";
  const statusLabel = value => ({ out: "Fuera", questionable: "En duda", doubtful: "Dudoso",
    probable: "Probable", available: "Disponible" }[value] || value || "Sin estado");
  const measures = ["home_ml", "away_ml", "home_plus20", "away_plus20"];

  root.hidden = false;
  root.append(el("div", "NBA · INVESTIGACIÓN PREGAME", "eyebrow"),
              el("h2", "Escenarios de rotación · ML y +20"));
  const status = el("p", "Cargando la corrida archivada…", "forecast-meta");
  status.setAttribute("role", "status");
  root.append(status);
  try {
    let response = await fetch("./data/nba-rotation-latest.json", { cache: "no-store" });
    if (response.status === 404) response = await fetch("./data/nba-rotation-pilot.json", { cache: "no-store" });
    if (!response.ok) throw new Error("Missing pilot");
    const report = await response.json();
    if (report.model_version !== "NBA_CONDITIONAL_ROTATION_PATH_V1" ||
        report.calibrated !== false || report.production_approved !== false ||
        !Number.isFinite(time(report.emitted_at_utc)) || !Array.isArray(report.games)) {
      throw new Error("Invalid pilot");
    }
    const valid = game => game.status === "research_scenario" &&
      time(report.emitted_at_utc) < time(game.tipoff_utc) &&
      ["reference", "conditional"].every(branch =>
        measures.every(key => probability(game.comparison?.[branch]?.path?.probabilities?.[key])));
    const count = report.games.filter(valid).length;
    const missingBaseline = report.games.filter(game =>
      game.blocked?.source?.includes("baseline_input_unavailable")).length;
    status.textContent = "Emisión archivada del " + formatTime.format(time(report.emitted_at_utc)) +
      " (Chile) · " + count + " de " + report.games.length + " partidos con simulación" +
      (missingBaseline ? " · " + missingBaseline + " sin captura base" : "");
    root.append(el("p", "Escenario experimental sin calibrar. La referencia usa el mismo simulador antes de redistribuir minutos. +20 significa alcanzar una ventaja de 20 puntos durante el partido.", "forecast-intro"));
    if (report.source_failure) {
      root.append(el("p", "Cobertura incompleta: " + (report.source_failure.detail || report.source_failure.status) +
        ". Los partidos sin captura base se muestran como PASS; no se reutilizan porcentajes de otra emisión.", "forecast-meta"));
    }
    root.append(el("p", "Las lesiones oficiales se muestran como un escenario condicional de minutos y producción histórica. No modifica el pronóstico base ni confirma quién jugará.", "forecast-intro"));
    const grid = el("div", undefined, "forecast-grid");
    for (const game of report.games) {
      const card = el("article", undefined, "forecast-card");
      card.append(el("h3", game.away_team + " — " + game.home_team));
      if (!valid(game)) {
        const reasons = [...new Set(Object.values(game.blocked || {}).flat().map(reason =>
          labels[String(reason).split(":")[0]] || "Evidencia insuficiente para simular"))];
        card.append(el("p", "Sin simulación", "forecast-state"));
        for (const reason of reasons) card.append(el("p", reason, "forecast-meta"));
      } else {
        const table = el("table", undefined, "forecast-table");
        const heading = el("tr");
        for (const title of ["Resultado", "Referencia", "Con bajas"]) {
          const cell = el("th", title);
          cell.scope = "col";
          heading.append(cell);
        }
        const head = el("thead");
        head.append(heading);
        const body = el("tbody");
        const titles = [game.home_team + " gana", game.away_team + " gana",
                        game.home_team + " alcanza +20", game.away_team + " alcanza +20"];
        for (const [i, key] of measures.entries()) {
          const row = el("tr");
          const title = el("th", titles[i]);
          title.scope = "row";
          row.append(title, ...["reference", "conditional"].map(branch =>
            el("td", formatPct.format(game.comparison[branch].path.probabilities[key]))));
          body.append(row);
        }
        table.append(head, body);
        card.append(table);
        card.append(el("p", "Disponibilidad condicional. Las tasas de pérdidas y la fatiga se mantienen fijas en ambas ramas.", "forecast-footnote"));
      }
      const impact = game.official_injury_impact;
      if (impact?.status === "research_only" && impact.teams) {
        const section = el("section", undefined, "nba-injury-impact");
        section.append(el("h4", "Impacto de lesiones oficiales · escenario condicional"));
        if (Number.isFinite(time(impact.emitted_at_utc))) {
          section.append(el("p", "Evidencia observada " + formatTime.format(time(impact.emitted_at_utc)) + " (Chile).", "forecast-meta"));
        }
        for (const [teamName, team] of Object.entries(impact.teams)) {
          const group = el("div", undefined, "nba-injury-team");
          group.append(el("h5", teamName + " · " + team.official_out_count + " baja(s) oficial(es)"));
          if (team.official_reported_players?.length) {
            const list = el("ul", undefined, "nba-injury-list");
            for (const player of team.official_reported_players) {
              const history = player.historical;
              const production = history?.per_game;
              const productionText = production
                ? " · hist.: " + number(production.points) + " pts / " + number(production.rebounds) + " reb / " + number(production.assists) + " ast por partido"
                : " · sin muestra histórica suficiente";
              const minutes = player.estimated_minutes_lost == null
                ? " · minutos históricos: —" : " · ~" + number(player.estimated_minutes_lost) + " min/partido";
              const minuteQuality = player.estimated_minutes_confidence === "limited"
                ? " · estimación con muestra limitada" : "";
              const sample = history?.sample_games ? " · muestra: " + history.sample_games + " partidos" : "";
              list.append(el("li", player.player + " · " + statusLabel(player.official_status) + minutes + minuteQuality + sample + productionText));
            }
            group.append(list);
          } else {
            const reportState = team.official_report_capture_status;
            const reportMessage = reportState === "report_not_retrieved"
              ? "No se obtuvo el informe oficial para esta captura."
              : reportState === "report_time_not_pregame"
                ? "El informe no tiene una hora válida anterior al inicio del partido."
                : reportState === "no_rows_for_fixture" || reportState === "report_rows_outside_fixture_rosters"
                  ? "No se pudieron asociar filas del informe oficial a este partido."
                  : "El informe fue capturado, pero no hay jugadores asociados a este equipo.";
            group.append(el("p", reportMessage, "forecast-meta"));
          }
          const scenario = team.minute_redistribution;
          if (scenario?.status === "conditional_historical_rotation_scenario") {
            group.append(el("p", "Redistribución estimada de minutos (base → escenario)", "forecast-meta"));
            const changes = scenario.changes.filter(row => row.minute_delta > 0.05);
            if (changes.length) {
              const list = el("ul", undefined, "nba-injury-list");
              for (const row of changes) {
                const extra = row.historical_output_delta_per_game;
                const extraText = extra
                  ? " · producción estimada: +" + number(extra.points) + " pts, +" + number(extra.rebounds) + " reb, +" + number(extra.assists) + " ast/partido"
                  : " · producción histórica insuficiente";
                list.append(el("li", row.player + " · " + number(row.baseline_minutes) + " → " + number(row.scenario_minutes) + " min (＋" + number(row.minute_delta) + ")" + extraText));
              }
              group.append(list);
            } else {
              group.append(el("p", "No hay cambios de minutos estimables con la evidencia disponible.", "forecast-meta"));
            }
          } else if (team.official_out_count) {
            const missingNames = (scenario?.missing_out_players || []).map(player => player.player).filter(Boolean);
            const detail = missingNames.length ? " · Sin historial suficiente: " + missingNames.join(", ") : "";
            group.append(el("p", "Redistribución no calculable: " + (labels[scenario?.status] || "faltan datos de rotación") + detail, "forecast-meta"));
          }
          group.append(el("p", team.scenario_assumption || "Escenario de investigación; la disponibilidad de los reemplazos no está confirmada.", "forecast-footnote"));
          group.append(el("p", "Jugadores sin disponibilidad confirmada: " + number(team.players_without_confirmed_availability, 0) + ". Probabilidades base sin cambios.", "forecast-footnote"));
          section.append(group);
        }
        card.append(section);
      }
      grid.append(card);
    }
    root.append(grid);
  } catch {
    status.textContent = "La corrida archivada no está disponible en este momento.";
  }
})();
