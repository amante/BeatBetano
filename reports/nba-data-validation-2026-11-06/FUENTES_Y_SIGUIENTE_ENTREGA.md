# NBA — cierre de auditoría de fuentes y evaluación histórica

6 de noviembre de 2026. Esta entrega amplía el PR consolidado #342. No autoriza
merge ni promoción del modelo. No se agregaron cuotas a los datos del modelo.

## Resultado operativo

La captura nueva, realizada aproximadamente a las 13:44 UTC (10:44 de Chile),
recuperó 9 partidos futuros, 18 plantillas y 313 jugadores. El PDF oficial de las
08:15 ET fue seleccionado desde el índice público NBA, no adivinado. Contiene
89 filas de estatus; la resolución derivada identifica 86, deja 3 sin coincidencia
y conserva 227 jugadores sin estatus explícito. Hay 21 estatus todavía inciertos
entre los identificados. Las 18 alineaciones recuperadas son proyectadas; ninguna
es un quinteto confirmado con IDs verificados. Son datos de una captura puntual,
no una promesa de disponibilidad de la fuente durante todo el día.

Se corrigió la comparación de comas/puntos en nombres conservando todos los
componentes, incluidos Jr./Sr. La coincidencia sigue exigiendo equipo e identidad
única. Ernest Udeh y Terrence Shannon quedan identificados; Christopher Cenac,
Khalifa Diop y Nae'Qwan Tomlin continúan sin coincidencia. No se asigna una baja
al jugador más parecido ni se presume sano a quien no figura en el informe.

La auditoría ahora enumera por equipo todos los requisitos V2, incluidos carga,
calendario y efectos sobre pérdidas. Resultado: **0/9 partidos listos**.

## Matriz de fuentes y aceptación

| Necesidad | Fuente comprobada | Resultado y siguiente criterio de aceptación |
|---|---|---|
| Calendario, resultados, plantillas y boxscores | ESPN, URLs y SHA256 en `live-capture/` | Captura obtenida. Exigir IDs únicos, equipos/fecha/marcador coincidentes y fuentes anteriores al corte de cada pronóstico. |
| Lesiones | [Índice NBA oficial](https://official.nba.com/nba-injury-report-2026-27-season) y PDF enlazado | PDF obtenido y reextraído. Resolver los 3 nombres restantes contra una plantilla oficial fechada; completar estatus activos sin inferirlos del silencio. |
| Titulares | Cascada existente; Rotowire en esta captura | 18 proyectados, 0 confirmados con IDs. Requiere confirmación explícita por ambos equipos antes del corte. |
| Minutos, carga, descanso y prórroga | Boxscores y calendario fechados | Dos juegos previos no cubren los 18 equipos actuales. Exigir calendario completo, último partido y todas las apariciones relevantes a la ventana de 48 horas. Historial parcial no significa carga cero. |
| ORtg/DRtg/pace agregados | NBA Stats, `leaguedashteamstats` | ReadTimeout; no datos nuevos. Las estimaciones de boxscore siguen disponibles, claramente diferenciadas de posesiones exactas. |
| Eficiencia de jugadores y on/off | NBA Stats, `leaguedashplayerstats`, `teamplayeronoffsummary` | Ambos ReadTimeout. Un on/off crudo, aun recuperado, no satisface efectos ajustados por rivales/rotaciones. Requiere método, referencia, muestra y corte documentados. |
| Posesiones normalizadas y quintetos en cancha | [Documentación pbpstats](https://pbpstats.readthedocs.io/en/stable/index.html), [API](https://api.pbpstats.com/docs) | Se comprobó la documentación y se probaron los cuatro equipos del 5/11: PHX/GSW/MIA HTTP 500, ORL ReadTimeout. Ninguna posesión importada. Exigir secuencia completa, todos los puntos incluidos FT/técnicos, reconciliación final, quintetos y minutos. |
| Alternativa de suministro | [Sportradar NBA play-by-play](https://developer.sportradar.com/basketball/reference/nba-play-by-play) | Documentación revisada; no se contrató servicio ni se dispone de acceso probado. Una exportación autorizada es otra ruta, sujeta a las mismas verificaciones; no garantiza efectos ajustados listos. |
| Reemplazos, roles y minutos/uso proyectados | Contrato del motor V2 | No hay export validado. Exigir todas las plantillas, suplentes y ausencias, método estimado con datos previos, límites de minutos y conservación de 240 minutos/uso. No asignar puntuaciones arbitrarias por nombre. |

Las pruebas de conectividad son observaciones de este intento: ni certifican que
una fuente siempre falle ni establecen que la documentación de una API garantice
su cobertura real. No se hicieron reintentos masivos ni se eludieron controles.
Los scripts de sondeo conservan sólo campos deportivos y rechazan sobrescrituras.

## Evaluación histórica realizada

Se reutilizó el historial congelado con digest verificado: 3.690 partidos,
1.230 por temporada final 2024/2025/2026, y 30 equipos con 82 apariciones por
cada temporada. Sin redescargar temporadas. La primera prepara el modelo;
las otras dos aportan 2.460 partidos puntuados cronológicamente.

| Modelo evaluado | n | Brier | Log loss | ECE descriptivo |
|---|---:|---:|---:|---:|
| Oficial, benchmark Elo | 2460 | 0.212063 | 0.612436 | 0.032285 |
| Baseline anterior, margen/descanso | 2460 | 0.209393 | 0.606755 | 0.032688 |
| Challenger completo V2 | 0 | N/D | N/D | N/D |

Menor es mejor para estas medidas. La mejora Brier emparejada del baseline
margen/descanso es 0.002670; intervalo percentil 95% por semanas y temporadas:
[0.001013, 0.004222]. Su ECE agregado es ligeramente mayor. Esto no certifica
calibración ni valida el motor completo de lesiones/reemplazos/+20. Los detalles
por temporada, bins, sensibilidad por días y semanas están en `evaluation/`.
Las probabilidades de los 2.460 partidos se conservan etiquetadas explícitamente
como reconstrucciones retrospectivas, no como emisiones pregame históricas.

Las temporadas ya fueron inspeccionadas y los coeficientes se incorporaron tras
su finalización. Se conserva la evaluación descriptiva, sin llamarla validación
independiente ni ajustar un calibrador con los mismos resultados que se puntúan.
El Challenger V2 no tiene snapshots numéricos elegibles para este conjunto:
no se pueden medir todavía sus mejoras, su calibración ni su capacidad +20.

## Evidencia observada del 5 de noviembre

Se reconciliaron las acciones deportivas archivadas con el marcador final y se
confirmaron las máximas de ambos equipos: PHX 30/ORL 6 y GSW 20/MIA 10. La fuente
además registra PHX 17–34 en triples, 25 pérdidas de Orlando y 36 puntos concedidos
por Orlando tras pérdidas. Son observaciones posteriores al partido; no se usan
para reconstruir lesiones o probabilidades pregame. Las bajas, Giannis y el
contexto de descanso aportados en el post-mortem siguen distinguidos de estas
verificaciones estadísticas; este informe no certifica todas esas afirmaciones.

Se detectó un problema en posesiones estimadas: se tomaban pérdidas individuales
antes que pérdidas totales del equipo. Ahora el campo `totalTurnovers` tiene
prioridad, conservando `turnovers` como alternativa cuando el total no existe.
En estos dos juegos, la estimación PHX pasa de 100.72 a 101.72; MIA de 106.12 a
109.12; GS de 102 a 103; ORL permanece en 101.56. La captura original es inmutable;
la corrección queda en resultados derivados. Nada de ello convierte la fórmula
FGA + .44×FTA − ORB + TOV en una secuencia de posesiones normalizadas.

## Condiciones para completar el paso 2 del Challenger

1. Obtener un lote autorizado de posesiones, quintetos y boxscores que supere
   reconciliación de identidad, marcador, duración, minutos y cobertura histórica.
2. Construir efectos ajustados, roles y proyecciones usando exclusivamente el
   tramo anterior al corte de cada partido; versionar método y parámetros.
3. Reservar periodos de ajuste, calibración y evaluación por orden temporal.
   Las temporadas ya inspeccionadas sólo dan evidencia retrospectiva. No declarar
   un periodo independiente sin demostrar que quedó fuera de la selección.
4. Comparar Oficial, baseline anterior y V2 en exactamente los mismos partidos
   elegibles. Registrar también excluidos y motivos; evaluar ML y +20 por ambos
   lados. +20 necesita trayectorias, nunca sólo margen final. No usar cuotas.
5. Mantener coeficientes congelados durante la evaluación; no ajustar con PHX/GSW.
   Ajustar un calibrador únicamente si existe tramo de calibración separado y
   evaluar su resultado fuera de ese tramo. Hasta entonces PASS.

**Dependencia externa pendiente:** datos completos/fechados o acceso funcional a
su proveedor. La auditoría y el backtest de los baselines están ejecutados; la
validación del Challenger completo permanece bloqueada por esa dependencia.
No se compró acceso, no se publicaron recomendaciones y no se hizo merge.

## Reproducir

Python 3.9+ con requests y pypdf. Usar rutas nuevas para cada salida.

```sh
python nba/data_validation_run.py \
  --capture reports/nba-data-validation-2026-11-06/live-capture \
  --archive reports/nba-2026-11-04 --output /tmp/nba-new-evaluation
python reports/nba-data-validation-2026-11-06/probe_advanced_sources.py \
  --output /tmp/nba-new-advanced-probe
python reports/nba-data-validation-2026-11-06/probe_possession_sources.py \
  --output /tmp/nba-new-possession-probe
python -m unittest discover -s nba/tests -q
```

La evaluación sin red reproduce las métricas y cobertura de los bytes archivados;
los sondeos de red pueden producir respuestas distintas en otro momento.
