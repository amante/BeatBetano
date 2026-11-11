"use strict";
(() => {
  const labels = { nba: "NBA", nfl: "NFL", nhl: "NHL", soccer: "Fútbol", tennis: "Tenis" };
  const fields = [
    ["created", "Creado"],
    ["connected", "Conectado"],
    ["affects_prediction", "Afecta porcentajes"]
  ];
  const root = document.getElementById("model-module-status");
  if (!root) return;
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const stage = (module) => {
    if (fields.every(([key]) => module[key])) return "Seguimiento y calibración";
    if (module.created && module.connected) return "Conectado · falta afectar porcentajes";
    if (module.created) return "Creado · falta conectar";
    return "Pendiente de creación";
  };
  const render = (registry, sport) => {
    const section = registry.sports?.[sport];
    if (!section) {
      root.replaceChildren(el("p", "No hay un inventario disponible para este deporte.", "module-lifecycle-empty"));
      return;
    }
    const modules = section.modules || [];
    const counts = Object.fromEntries(fields.map(([key]) => [key, modules.filter(m => m[key]).length]));
    const closed = modules.filter(m => fields.every(([key]) => m[key])).length;
    const header = root.querySelector("[data-module-lifecycle-header]");
    header.replaceChildren(
      el("div", "ESTADO DEL MODELO · " + labels[sport].toUpperCase(), "eyebrow"),
      el("h2", "Módulos y conexión con la predicción"),
      el("p", "Un módulo solo pasa a seguimiento y calibración cuando está creado, conectado y cambia los porcentajes del mercado indicado.")
    );
    const summary = root.querySelector("[data-module-lifecycle-summary]");
    summary.replaceChildren(
      ...fields.map(([key, label]) => el("span", `${label}: ${counts[key]}/${modules.length}`, "module-lifecycle-count")),
      el("span", `Seguimiento: ${closed}/${modules.length}`, "module-lifecycle-count module-lifecycle-count--closed")
    );
    const list = root.querySelector("[data-module-lifecycle-list]");
    list.replaceChildren(...modules.map(module => {
      const card = el("article", undefined, "module-lifecycle-card");
      card.dataset.stage = stage(module) === "Seguimiento y calibración" ? "tracking" : "open";
      const top = el("div", undefined, "module-lifecycle-card__top");
      top.append(el("h3", module.name), el("span", stage(module), "module-lifecycle-stage"));
      const flags = el("div", undefined, "module-lifecycle-flags");
      for (const [key, label] of fields) {
        const active = module[key] === true;
        const flag = el("span", `${active ? "✓" : "○"} ${label}`, `module-lifecycle-flag ${active ? "is-yes" : "is-no"}`);
        flag.setAttribute("aria-label", `${label}: ${active ? "Sí" : "No"}`);
        flags.append(flag);
      }
      const details = el("details", undefined, "module-lifecycle-details");
      details.append(el("summary", "Alcance y evidencia"), el("p", module.scope || "Sin alcance documentado."), el("p", module.note || ""), el("small", "Evidencia: " + (module.evidence || "No registrada.")));
      card.append(top, flags, details);
      return card;
    }));
    root.dataset.inventoryState = section.inventory_state || "unknown";
    root.querySelector("[data-module-lifecycle-asof]").textContent = "Auditoría del inventario: " + (registry.audited_at || "sin fecha") + (section.inventory_state === "audited" ? " · revisión de código y flujo" : " · inventario de hoja de ruta y revisión de código");
  };
  const sport = new URLSearchParams(location.search).get("sport");
  fetch("./data/model-modules.json", { cache: "no-store" })
    .then(response => { if (!response.ok) throw new Error("HTTP " + response.status); return response.json(); })
    .then(registry => render(registry, sport))
    .catch(() => root.replaceChildren(el("p", "No se pudo cargar el estado de los módulos.", "module-lifecycle-empty")));
})();
