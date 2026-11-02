# Evaluación de los modelos deportivos y plan de avance

**Fecha:** 2 de noviembre de 2026, America/Santiago. **Repositorio auditado:** amante/BeatBetano, revisión `22007939de94a4c397e92394bc6b0e328d8042b9`.

## Decisión principal

Consolidar primero NHL como producto experimental medible; recuperar la operación y validar el candidato NBA; concentrar NFL en el challenger EPA. Fútbol y tenis requieren construir modelos específicos antes de presentarlos como capacidades predictivas. No hay evidencia revisada que permita certificar hoy un modelo deportivo completo como independiente y listo para producción.

La madurez de la interfaz no equivale a madurez predictiva. NHL es el más integrado en la web; NBA tiene la evidencia histórica comparativa más amplia de los reportes examinados; NFL EPA muestra una mejora pequeña que merece seguimiento. Las tres afirmaciones pueden ser ciertas a la vez.

## Alcance y límites de esta evaluación

Se revisaron código, contratos, workflows, reportes publicados y logs de ejecuciones reales. Se consultaron las últimas ejecuciones de doce workflows relevantes; esto no es una revisión exhaustiva de cada ejecución histórica del repositorio. No se volvieron a entrenar todos los modelos ni se reprodujeron desde cero los backtests históricos completos. Se ejecutó el post mortem NHL del 1 de noviembre con fuentes oficiales y 22 pruebas existentes del scoring/reconstrucción/comparación. Las cifras históricas de NBA/NFL/NHL que siguen provienen de sus ejecuciones identificadas, no de una nueva certificación externa.

Los README y ROADMAP contienen declaraciones antiguas: por ejemplo, el roadmap multideporte afirma que solo existe NBA, mientras el código ya tiene adaptadores NBA/NFL/NHL. Por eso la evaluación prioriza el código y las salidas verificadas frente al nombre de un módulo o workflow.

## Inventario por deporte

| Deporte | Implementación comprobada | Evidencia predictiva revisada | Principal brecha | Decisión |
|---|---|---|---|---|
| NHL | Baseline por resultados para ML, tiempo regular, +3 local/visitante y primero en +3; challenger de equipos; investigación de arqueros; publicación web, calendario y ejecución protegida | Backtests y registros pregame; muestra prospectiva todavía pequeña; post mortem nuevo de cinco encuentros | Calibración por mercado, prueba temporal de variables de arqueros/plantillas y cierre fiable del ciclo de evaluación | Mantener baseline experimental; no promover challenger ni añadir ajustes manuales |
| NBA | Elo, challenger por forma/descanso, rutas híbridas, capturas y módulos de lesiones, quintetos, minutos y posesiones | 3.690 partidos históricos, 2.460 de evaluación en dos temporadas; challenger mejora sobre Elo en ambas | Capa deportiva no operativa en la última ejecución revisada; guardrails ajustados después de observar los holdouts | Segundo foco: restablecer fuentes y evaluar prospectivamente el candidato congelado |
| NFL | Elo, challenger por forma, challenger EPA/success rate, módulos de disponibilidad/inactivos y reconciliación | 569 partidos comparados; EPA mejora modestamente, forma prácticamente no mejora | Fuentes y validación incremental de QB/lesiones/clima; integración y empates aún limitada | Priorizar EPA en sombra; conservar Elo como referencia |
| Fútbol | Contrato multideporte, extracción de calendario/resultados y componente genérico de asignación | No se encontró modelo específico entrenado y evaluado | Historial por competición, empate, xG y evidencia de alineaciones | Diseñar MVP de una sola liga; no mostrar probabilidades inventadas |
| Tenis | Contrato multideporte y extracción ATP/WTA de calendario/resultados | No se encontró modelo específico entrenado y evaluado | Identidad de jugadores, superficie, retiros/walkovers y baseline | MVP acotado a un circuito y formato; iniciar después de estabilizar los deportes existentes |

Un extractor de calendario, un esquema validado, un archivo de tests o un módulo genérico de reparto de minutos no constituyen un modelo predictivo de ese deporte.

## NHL: evaluación de cada familia

### Baseline experimental y cinco mercados

La web publica `outcome-only-206-frozen-params`. No incorpora por ello una estimación completa de impacto de arqueros, bajas, líneas o PP/PK. El reporte `pulso-nhl-research.json` de la revisión auditada mantiene cero predicciones oficiales y bloquea el modelo deportivo completo por plantillas no conectadas, confirmación/identidad de arqueros insuficiente y tasas de gol sin calibración.

La evaluación prospectiva publicada antes del nuevo post mortem contiene **19 partidos por mercado**, no 95 partidos: 95 es el número de combinaciones partido–mercado puntuadas. La comparación ML publicada baseline/challenger tiene **13 partidos emparejados**: Brier 0,225450 frente a 0,233697 y log loss 0,643484 frente a 0,659983. Es evidencia preliminar favorable al baseline, con muestra demasiado pequeña para certificar superioridad general.

El nuevo post mortem del **1 de noviembre** agrega una evaluación separada, sin sumar observaciones repetidas: ML 4/5, Brier 0,234159; tiempo regular 4/5; primero en +3 0/5 para la clase modal. En la comparación emparejada de esa jornada hay cuatro juegos: baseline Brier 0,248002 y challenger 0,264724. No se mezcla ese n=4 con el n=5 del baseline de toda la jornada. Ver el informe y los JSON en `reports/nhl/2026-11-01/`.

**Decisiones por mercado:** ML puede seguir como referencia experimental. Tiempo regular exige revisar por separado la probabilidad de empate. Los eventos +3 requieren auditoría de etiquetas y calibración basada en trayectorias de goles; no basta el margen final. “Primero en +3” debe conservar la clase “ninguno”, pero su frecuencia y calibración deben vigilarse en una cohorte amplia; no se elimina la clase por una jornada adversa.

### Challenger de equipos y modelo con arqueros

El gate #271, con **524 partidos de holdout**, registra que añadir arqueros no mejora incrementalmente: equipos Brier 0,245917 / log loss 0,684955; combinación con arqueros 0,245972 / 0,685059. La combinación supera una constante más débil, pero ese no es el benchmark decisivo.

La comparación #272 sobre los mismos 524 juegos muestra que el baseline congelado #218 sigue siendo mejor que el candidato de equipos: **0,245732 / 0,684561** frente a **0,245917 / 0,684955**. Por tanto, no hay evidencia para reemplazar el baseline actual. Tampoco queda acreditada en ese gate la disponibilidad histórica pregame de las identidades/estados de arqueros.

**Siguiente experimento:** una variable deportiva a la vez, con versiones congeladas y fecha real de disponibilidad. Comparar equipos, arquero y combinación frente al baseline fuerte en los mismos partidos, con intervalos de incertidumbre. Una mejora contra una constante no autoriza promoción.

Fuentes: [gate #271](https://github.com/amante/BeatBetano/actions/runs/41263762604), [benchmark #272](https://github.com/amante/BeatBetano/actions/runs/41264908851), [investigación de arqueros #269](https://github.com/amante/BeatBetano/actions/runs/41261897801).

## NBA: evaluación de cada familia

### Elo y challenger por forma/descanso

El backtest auditó **3.690 encuentros de temporada regular**: una temporada de arranque y dos de evaluación, con 1.230 partidos cada una. Los años 2025 y 2026 en el reporte son años de fin de temporada.

| Evaluación | n | Brier Elo | Brier challenger | Log loss Elo | Log loss challenger |
|---|---:|---:|---:|---:|---:|
| 2024–25 | 1.230 | 0,214452 | 0,212050 | 0,616743 | 0,611603 |
| 2025–26 | 1.230 | 0,209673 | 0,206736 | 0,608129 | 0,601908 |

El challenger mejora ambas métricas en las dos temporadas, pero el propio reporte lo conserva como candidato y no aceptado para producción. Hace falta confirmar la historia de selección de parámetros, intervalos emparejados y rendimiento futuro con la versión congelada.

### Híbrido y guardrails

El híbrido/guarded parece mejorar algo más, pero su reporte declara explícitamente que los guardrails fueron elegidos tras inspeccionar esas temporadas: **esa evaluación ya no es independiente para esa regla**. No utilizar la mejora observada como prueba de promoción. Congelar la regla y evaluarla en datos posteriores intactos.

### Lesiones, quintetos, minutos y posesiones

Hay mucho código de infraestructura, pero la última ejecución `nba-auto-history` examinada produjo cuatro encuentros con **cero quintetos confirmados, cero partidos con capa deportiva completa y cero probabilidades finales integradas**. La fuente oficial de lesiones devolvió HTTP 403. El pipeline terminó correctamente porque bloqueó ajustes sin evidencia; no porque hubiese conseguido el modelo completo.

Las conversiones de posesiones/margen a probabilidad y sus pesos/sigma son hipótesis experimentales, no calibración independiente. El detector NBA de ventaja +20 cuenta un hecho observado en play-by-play; por sí solo no calcula P(+20) antes del partido. Las apuestas de jugadores necesitan su propio modelo, historial y validación.

**Siguiente paso:** reparar una ruta verificable de lesiones/quintetos y sus fechas; medir cobertura y conflictos antes de construir más capas. Después, probar la contribución incremental de disponibilidad y minutos frente al baseline estadístico, con probabilidades integradas nulas cuando no haya evidencia suficiente.

Fuentes: [backtest de tres temporadas](https://github.com/amante/BeatBetano/actions/runs/40616128083), [ejecución automática examinada](https://github.com/amante/BeatBetano/actions/runs/40441998232).

## NFL: evaluación de cada familia

| Modelo, misma evaluación de 569 juegos | Brier | Log loss | Lectura |
|---|---:|---:|---|
| Elo | 0,223226 | 0,636953 | Referencia operacional |
| Forma reciente | 0,223260 | 0,636972 | Prácticamente igual, ligeramente peor |
| EPA/success rate | 0,220487 | 0,629638 | Mejora pequeña que merece validación adicional |

EPA mejora Brier en aproximadamente 0,002739 y log loss en 0,007316. No basta para afirmar significancia estadística ni rentabilidad; hacen falta intervalos emparejados, estabilidad por temporada y un seguimiento posterior congelado.

`NFL hoy` conserva probabilidades oficiales/finales nulas y reconoce faltantes en inactivos, titulares, clima, matchups y calibración independiente. El baseline excluye empates, lo cual debe declararse y resolverse si se pretende cobertura completa de mercados con empate. Los módulos de jugadores y posiciones no prueban por sí solos un sistema de props calibrado; no existe evidencia revisada de una combinada conjunta validada.

**Siguiente paso:** mantener Elo y EPA en paralelo, agregar primero QB/inactivos verificados y probar ese delta de forma aislada. Después OL/defensa y clima, siempre que existan fuentes pregame con fecha. No ampliar props antes de validar oportunidades/snaps y dependencia entre selecciones.

Fuentes: [challenger por forma](https://github.com/amante/BeatBetano/actions/runs/40032224503), [challenger EPA](https://github.com/amante/BeatBetano/actions/runs/40032224550), [NFL hoy](https://github.com/amante/BeatBetano/actions/runs/40337008388).

## Fútbol y tenis: MVP concretos

**Fútbol:** escoger una liga y una definición de encuentro/temporada; normalizar identidades y resultados; separar 90 minutos de prórroga; construir un baseline Poisson con fuerzas de ataque/defensa y, si se justifica, corrección Dixon–Coles. Evaluar P(local/empate/visitante), calibración por clase y comparación con tasas históricas/localía. Incorporar xG solo si hay una fuente consistente, autorizada y temporalmente admisible. Las alineaciones y ausencias son una etapa posterior, medida por ablación.

**Tenis:** escoger un circuito y un formato; normalizar jugadores, superficie y fechas; tratar retiros y walkovers con reglas explícitas; construir Elo general y por superficie con ajuste por tamaño de muestra. Evaluar ganador con split cronológico por torneos/semanas y seguimiento futuro. Fatiga, viajes, H2H y recuperación tras retiro son candidatos de variables, no ponderaciones manuales asumidas.

No abrir ambos MVP a la vez mientras NHL/NBA/NFL requieran mantenimiento operativo. Si hay que elegir uno primero, propongo tenis por el objetivo binario acotado; es una decisión de alcance y recursos, no una afirmación de mayor potencial predictivo.

## Problemas compartidos que frenan el avance

1. **Publicación general de calendarios:** la última ejecución revisada del feed de cinco deportes obtuvo 95 eventos sin errores de fuentes, pero falló al guardar archivos ignorados por Git. El éxito del calendario NHL no resuelve NBA/NFL/fútbol/tenis. Corregir la persistencia y comprobar la publicación extremo a extremo. [Ejecución con fallo](https://github.com/amante/BeatBetano/actions/runs/41368495429).
2. **Resultados y trazabilidad:** conservar pronósticos por emisión, la hora real de captura, versión del código/datos y resultados oficiales. Hashes ayudan a detectar cambios, pero no certifican por sí solos cuándo se creó una predicción. Mantener una política única de evaluación de emisiones repetidas.
3. **Registro del modelo:** el registro compartido valida estructura y declaraciones. Falta demostrar que todas las rutas de producción lo utilizan con evidencia independiente de los reportes; una etiqueta `independently_validated` no debe bastar para aprobar un modelo.
4. **Documentación y nombres:** actualizar README/ROADMAP y etiquetas “oficial”, “challenger”, “híbrido” para que reflejen estado real. Un workflow verde solo acredita que terminó conforme a sus controles.
5. **Reutilización temporal:** los datos postgame del post mortem se guardan con disponibilidad temporal y separados de variables pregame. Una hipótesis aprendida de un día no puede validarse en ese mismo día como si nunca se hubiese visto.

## Plan de ejecución propuesto

Fechas orientativas desde el 2 de noviembre, sujetas a acceso a fuentes y revisiones. Se planifican entregables; la validación predictiva no queda aprobada porque venza una fecha.

| Orden | Ventana propuesta | Entregable | Criterio de aceptación |
|---|---|---|---|
| P0 | 2–4 nov | Inventario único y estados reales por modelo; corregir persistencia del feed general; integrar post mortem fechado | Cada deporte distingue calendario, pronóstico, experimento y resultado; un ciclo captura→persistencia→web comprobado; cinco resultados NHL y 25 mercados trazables sin duplicados |
| P1 | 5–11 nov | NHL: reconciliación diaria, registro de aprendizaje y evaluación por mercado; revisar frescura de capturas | Resultados finales auditados por PBP; una emisión por juego/modelo/mercado; métricas por fecha y acumuladas; captura caducada o faltante visible; ningún ajuste no validado |
| P2 | 12–18 nov | NBA: restablecer fuentes de lesiones/quintetos; congelar Elo/challenger/híbrido | Cobertura, conflictos y antigüedad cuantificados; cero confirmaciones fabricadas; congelación de parámetros antes de evaluar el tramo posterior; incertidumbre y ablaciones publicadas |
| P3 | 19 nov–1 dic | NFL: evaluación emparejada Elo/EPA y primer experimento QB/inactivos | Mismos partidos y versiones comparadas; resultados por temporada; intervalo de la mejora y pruebas de ausencia de fuga; sin promoción si el beneficio no se sostiene |
| P4 | Tras estabilizar P0–P3 | MVP de tenis o fútbol, uno solo | Fuente, historial y reglas de liquidación definidos; baseline reproducible; cobertura validada; test temporal independiente antes de publicarlo como modelo |

### Orden de PRs, sin mezclar apuestas de desarrollo

- **PR A — Evidencia y revisión:** guardar este plan, post mortem NHL 1/nov, cohortes seleccionadas, fuentes y aprendizaje en cuarentena. Sin cambiar parámetros.
- **PR B — Operación común:** arreglar guardado del feed de cinco deportes; comprobar calendario, fechas, resultados y publicación. Actualizar documentación de estados.
- **PR C — NHL medible:** ejecutar post mortem por fecha automáticamente; enlazar reportes diarios/acumulados; mantener registros de versiones y aprendizaje. Usar el caso ANA–OTT como regresión de objetivos +3.
- **PR D — NBA candidato:** resolver la fuente y medir cobertura; activar seguimiento congelado del candidato estadístico, sin mezclarlo con lesiones no verificadas.
- **PR E — NFL candidato:** medir EPA con incertidumbre y estabilidad; añadir QB/inactivos como experimento separado.
- **PR F — Primer nuevo deporte:** implementar el MVP elegido; no activar ambos deportes nuevos simultáneamente.

### Puerta de promoción de una versión

Una nueva versión solo puede avanzar si: (a) sus variables estaban disponibles antes del evento; (b) dataset, parámetros y código están versionados; (c) el entrenamiento y la calibración no usan el holdout; (d) se compara con el baseline fuerte sobre la misma cohorte; (e) la mejora de Brier/log loss y sus intervalos están documentados, con calibración por clases y segmentos; (f) resiste una muestra posterior congelada sin degradaciones materiales; (g) existe una revisión independiente documentada. El umbral de mejora, la tolerancia de degradación y el tamaño de muestra se fijan antes del experimento según precisión/potencia y coste del error, no después de observar resultados.

No usar “200 partidos” o “30 días” como certificado automático. No comparar Brier entre deportes/objetivos con distinta composición como una tabla de posiciones. No usar acierto bruto, una jornada ganadora, un hash o tests unitarios como sustituto de validación de probabilidades. No se afirma ROI ni valor de apuesta: no se evaluaron precios ni costes.

## Primer paso recomendado

Conservar el baseline NHL experimental y cerrar su ciclo diario de evaluación; reparar el feed común para que los demás deportes tengan una base operativa real. En paralelo lógico —sin exigir trabajo simultáneo—, preparar NBA como siguiente candidato por su evidencia histórica y NFL EPA como tercera línea. Las hipótesis del 1 de noviembre ya están registradas y no modifican los pesos en vivo.
