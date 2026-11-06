# NBA — Fuentes y validación histórica

Oficial sigue como benchmark. Challenger completo V2: investigación, PASS.

## Cobertura de la captura

| Evidencia | Cobertura |
|---|---:|
| Partidos / equipos | 9 / 18 |
| roster_members | 313 |
| official_status_claims | 86 |
| unknown_status_players | 227 |
| unresolved_official_status_claims | 21 |
| observed_minutes_players | 0 |
| confirmed_starting_fives_with_verified_ids | 0 |
| normalized_possessions | 0 |
| adjusted_player_effects | 0 |
| verified_load_and_schedule_teams | 0 |
| Reclamos oficiales sin identidad resuelta | 3 |
| Partidos aptos para el motor completo | 0 |

Las fuentes de titulares proyectados no certifican IDs ni disponibilidad completa.
Minutos observados y posesiones estimadas no son proyecciones ni posesiones normalizadas.

## Evaluación retrospectiva ejecutada

| Modelo / temporada final | n | Brier | Log loss | ECE |
|---|---:|---:|---:|---:|
| Oficial Elo / 2025 | 1230 | 0.214452 | 0.616743 | 0.036882 |
| Baseline margen/descanso (no V2) / 2025 | 1230 | 0.212050 | 0.611603 | 0.038015 |
| Oficial Elo / 2026 | 1230 | 0.209673 | 0.608129 | 0.027688 |
| Baseline margen/descanso (no V2) / 2026 | 1230 | 0.206736 | 0.601908 | 0.040327 |
| Oficial Elo / pooled | 2460 | 0.212063 | 0.612436 | 0.032285 |
| Baseline margen/descanso (no V2) / pooled | 2460 | 0.209393 | 0.606755 | 0.032688 |

Challenger V2: 0 partidos puntuados; no se ajustó calibrador.
ML/+20 sin pronósticos elegibles: Brier/log loss NULL, sin aciertos ni DUAL.
Este recorrido usa resultados anteriores, pero las temporadas ya fueron inspeccionadas: no acredita independencia de selección.

## Trayectorias observadas, sin predicciones retrospectivas

| Partido | Resultado | Máxima local / visitante |
|---|---|---|
| ORL @ PHX | 104–117 | 30 / 6 |
| MIA @ GS | 100–120 | 20 / 10 |

## Bloqueos por equipo

| Requisito | Equipos bloqueados |
|---|---:|
| complete_active_status | 18 |
| adjusted_player_on_off | 18 |
| replacement_roles_and_quality | 18 |
| projected_minutes_and_usage | 18 |
| normalized_possessions | 18 |
| independent_holdout_validation | 18 |
| player_committed_and_forced_turnover_on_off | 18 |
| verified_last_48h_load | 18 |
| complete_previous_game_schedule | 18 |
| verified_starting_five_ids | 18 |
| official_claim_missing_from_roster | 2 |

Próximas entradas necesarias: export autorizado de posesiones y alineaciones, efectos ajustados de jugadores con fecha de corte, roles/reemplazos, minutos/uso proyectados, carga y calendario completos.
No se sustituyen con on/off crudo, promedios de minutos o datos recuperados después del partido.

Fuentes: [NBA Injury Reports](https://official.nba.com/nba-injury-report-2026-27-season), [NBA Stats Glossary](https://www.nba.com/stats/help/glossary), ESPN (URLs y hashes exactos en la captura).
Sin cuotas como entradas. Sin promoción automática ni merge.
