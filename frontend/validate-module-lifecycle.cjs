"use strict";
const fs = require("node:fs");
const registry = JSON.parse(fs.readFileSync("frontend/data/model-modules.json", "utf8"));
const sports = ["nba", "nfl", "nhl", "soccer", "tennis"];
const fields = ["created", "connected", "affects_prediction"];
if (registry.schema_version !== 1 || !registry.definitions || !registry.sports) throw new Error("Invalid lifecycle registry header");
for (const sport of sports) {
  const modules = registry.sports[sport]?.modules;
  if (!Array.isArray(modules) || modules.length === 0) throw new Error(`Missing module inventory: ${sport}`);
  const ids = new Set();
  for (const module of modules) {
    if (!module.id || !module.name || !module.evidence || !module.scope || !module.note) throw new Error(`Incomplete module record: ${sport}`);
    if (ids.has(module.id)) throw new Error(`Duplicate module: ${sport}/${module.id}`);
    ids.add(module.id);
    for (const field of fields) if (typeof module[field] !== "boolean") throw new Error(`Missing boolean ${field}: ${sport}/${module.id}`);
    if (module.connected && !module.created) throw new Error(`Connected without created: ${sport}/${module.id}`);
    if (module.affects_prediction && !module.connected) throw new Error(`Affects without connected: ${sport}/${module.id}`);
  }
}
console.log("Module lifecycle inventory valid for all five sports.");
