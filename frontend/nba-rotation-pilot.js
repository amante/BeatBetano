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
    missing_rotation_scenario: "Escenario de rotación ausente"
  };
  const el = (tag, value, className) => {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const time = value => Date.parse(value);
  const probability = value => typeof value === "number" && value >= 0 && value <= 1;
  const measures = ["home_ml", "away_ml", "home_plus20", "away_plus20"];

  root.hidden = false;
  root.append(el("div", "NBA · INVESTIGACIÓN PREGAME", "eyebrow"),
              el("h2", "Escenarios de rotación · ML y +20"));
  const status = el("p", "Cargando la corrida archivada…", "forecast-meta");
  status.setAttribute("role", "status");
  root.append(status);
  try {
    const response = await fetch("./data/nba-rotation-pilot.json", { cache: "no-store" });
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
    status.textContent = "Emisión archivada del " + formatTime.format(time(report.emitted_at_utc)) +
      " (Chile) · " + count + " de " + report.games.length + " partidos con simulación";
    root.append(el("p", "Escenario experimental sin calibrar. La referencia usa el mismo simulador antes de redistribuir minutos. +20 significa alcanzar una ventaja de 20 puntos durante el partido.", "forecast-intro"));
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
      grid.append(card);
    }
    root.append(grid);
  } catch {
    status.textContent = "La corrida archivada no está disponible en este momento.";
  }
})();
