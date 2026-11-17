# NBA: descanso, B2B, viajes y husos horarios

## Estado del módulo

- **Creado:** sí.
- **Conectado a la corrida NBA:** sí. El contexto se construye en `nba/pregame_module_bundle.py`; el candidato histórico se calcula en `nba/travel_probability.py`; PULSO lo muestra dentro de la ficha del partido.
- **Afecta porcentajes:** solo como candidato experimental cuando la validación cronológica mejora simultáneamente Brier y log loss en la muestra de reserva. No es un ajuste certificado ni se activa por copiar efectos publicados.

## Variables capturadas antes del partido

Para cada equipo se calcula:

- Descanso aproximado en días y horas entre inicios de partidos.
- B2B estimado con la fecha local de cada arena y un máximo de 36 horas entre inicios.
- Secuencia de sede en B2B: local→local, local→visita, visita→local y visita→visita.
- Partidos disputados en las ventanas previas de 4 y 7 días.
- Distancia aproximada del último tramo y distancia acumulada entre sedes observadas en los 7 días previos.
- Cambio horario firmado y acumulado, y hora de inicio expresada según el huso horario del partido anterior.
- Interacción entre distancia y hora biológica estimada. Las señales cíclicas de hora evitan tratar 23:00 y 01:00 como si estuvieran separadas por 22 horas.

La comparación del encuentro se hace entre ambos equipos. Los indicadores describen el calendario observado y no aseguran el itinerario real de vuelos, sueño ni recuperación.

## Cómo entra en la fórmula

El Challenger ya tenía una señal genérica experimental por días de descanso. El ajuste de viaje existente usaba distancia y cambio de huso. Esta ampliación agrega explícitamente B2B y su sede anterior, enfrentamiento descansado-vs-B2B, carga de partidos reciente, hora circadiana aproximada y acumulación de trayectos.

Los coeficientes se estiman solo con partidos anteriores a la captura y se evalúan en un bloque cronológico posterior. El candidato se aplica únicamente si reduce **ambas** métricas frente a su base: Brier y log loss. Si falta muestra o no mejora las dos, la predicción mantiene sus porcentajes y PULSO muestra por qué no se aplicó. El corte de entrenamiento/reserva y el límite del ajuste permanecen controlados por el evaluador existente.

Los artículos de investigación justifican medir estos factores e interacciones; no son coeficientes de la fórmula. La calibración usa la historia NBA propia del repositorio.

## Límites de interpretación

- Los kilómetros son distancia de gran círculo entre arenas, no ruta aérea.
- “Descanso” es tipoff-a-tipoff; no se conoce el término exacto del partido previo.
- B2B es una aproximación basada en fechas locales y horas de inicio.
- La hora del reloj biológico se aproxima con el huso de la sede del partido anterior. No se conocen hábitos individuales, sueño, hora de viaje ni aclimatación real.
- No se infiere que un viaje al Este sea siempre peor: la dirección se combina con hora de juego, distancia y secuencia, y los coeficientes deben superar validación fuera de muestra.

## Evidencia científica consultada

- Charest et al. (2021), *Impacts of travel distance and travel direction on back-to-back games in the NBA*. [PubMed](https://pubmed.ncbi.nlm.nih.gov/34170248/)
- Cook et al. (2022), *Associations of circadian change, travel distance, and their interaction with NBA performance*. [PubMed](https://pubmed.ncbi.nlm.nih.gov/35980109/)
- Charest et al. (2022), *Eastward Jet Lag is Associated with Impaired Performance and Game Outcome in the NBA*. [Frontiers / PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9245584/)
