# Fútbol: revisión de pasos y propuesta de modelo base

Fecha: 2 de noviembre de 2026. Esta es una propuesta de implementación, no un modelo ya entrenado.

## Qué existe hoy y qué falta

- `frontend/collect_daily.py` obtiene calendario y resultados de Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Champions, Primera División de Chile y MLS. No produce probabilidades.
- `multisport/contract.py` reconoce fútbol y exige local/empate/visitante cuando se publica una probabilidad final. Es una validación estructural; no prueba cobertura ni precisión.
- Hay utilidades de procedencia, registro de modelos y protocolos históricos. El adaptador de modelos implementado solo admite NBA/NFL/NHL; fútbol necesita su propio adaptador.
- No hay un paquete `soccer/` con entrenamiento, evaluación, pronósticos pregame y liquidación específicos. El componente genérico de minutos no constituye un predictor de fútbol.
- El feed compartido necesita reparar su persistencia: la ejecución examinada del 2 de noviembre obtuvo eventos, pero falló al guardar rutas ignoradas por Git. Esta corrección es un requisito operativo, no una mejora estadística.
- El Worker actual solo autoriza el workflow NHL. Fútbol requerirá un workflow y una ruta autorizada propios; no se reutilizará la ruta NHL con parámetros arbitrarios.

## Alcance inicial recomendado

**Una liga, un mercado y un modelo transparente.** Propongo Premier League como supuesto inicial de trabajo, porque ya hay un identificador de proveedor configurado y es posible auditar un formato de liga regular. La elección se confirma antes de construir el histórico; si la prioridad comercial es Chile, se cambia el alcance y se auditan sus propios formatos y fuentes.

El objetivo V0.1 es predecir **P(local), P(empate) y P(visitante) al término de los 90 minutos más descuento**. No se incluyen prórroga, penales, copas, combinadas, props, tiros ni tarjetas. No se utilizan cuotas para construir variables, ajustar parámetros o completar probabilidades.

La primera versión usará goles históricos, ataque/defensa de los equipos y localía. xG, lesiones, alineaciones, táctica y fatiga se consideran mejoras posteriores, cada una con evidencia pregame y una prueba incremental. No se inventarán datos faltantes ni se presentará ese primer modelo como si incluyera plantillas.

## Plan de datos

1. Elegir una fuente histórica de resultados y una referencia para contrastar el calendario. Versionar las respuestas originales con URL, fecha de captura, licencia/condiciones, identificadores y SHA-256.
2. Normalizar `competition_id`, `season`, `event_id`, `home_team_id`, `away_team_id`, fecha/hora UTC, fecha local de competición, estado y marcador de 90 minutos. Mantener una tabla de equivalencias de equipos; no unir partidos solo por nombres o por una hora provisional.
3. Separar resultados finalizados de fixtures futuros. Para pregame, los marcadores del encuentro objetivo deben ser nulos. Una fila histórica sin hora verificable sirve para ciertos backtests por fecha, pero no acredita una captura pregame a una hora concreta.
4. Validar duplicados, partidos aplazados, cambios de fecha, ascensos/descensos, identidad local/visitante y cobertura contra el calendario esperado de cada temporada. Nunca usar el número de filas disponibles como prueba de integridad.
5. Recopilar cinco temporadas completas si la fuente permite una cobertura verificable. Para una liga regular de 20 equipos con ida y vuelta, 380 encuentros por temporada es una expectativa estructural que debe contrastarse; no se aplica ciegamente a otra competición/formato.
6. Reparar la publicación común y añadir un calendario de fútbol con fechas futuras, caché controlada y mensajes explícitos de datos no disponibles.

Como candidato de resultados, OpenFootball declara datos de fixtures y resultados en JSON y licencia CC0, sin API key; hay que comprobar las temporadas concretas y su integridad antes de adoptarlo. Fuente primaria: [OpenFootball](https://github.com/openfootball/football.json). Esto es una recomendación para auditar la fuente, no una garantía de cobertura o actualización para la temporada elegida.

Los datos abiertos de StatsBomb/Hudl cubren determinadas ligas/temporadas y tienen sus condiciones de uso; no deben asumirse como un feed vivo completo de todas las competiciones. Los dejaría para una segunda fase si su cobertura encaja con el experimento de eventos/xG. Fuente primaria: [StatsBomb Open Data](https://github.com/hudl/open-data/blob/master/README.md).

## Modelo V0.1: Poisson regularizado de ataque/defensa

Estimar las tasas de gol de ambos equipos a partir de datos anteriores al partido:

- `log(lambda_local) = nivel_liga + localia + ataque_local - defensa_visitante`
- `log(lambda_visitante) = nivel_liga + ataque_visitante - defensa_local`

Aplicar restricciones de identificación y regularización para evitar que pocos partidos produzcan fuerzas extremas. Los equipos recién ascendidos parten de un prior documentado y conservador; no reciben retrospectivamente una fuerza estimada con resultados futuros.

A partir de la distribución conjunta de goles, sumar la probabilidad de marcadores con local ganador, empate o visitante ganador. La matriz debe ampliar su cola hasta que la masa omitida esté bajo una tolerancia predefinida y registrar la normalización; no truncar silenciosamente marcadores altos. Las tres probabilidades deben ser finitas, estar dentro de rango y sumar uno.

El modelo Poisson independiente es un punto de partida comprobable. Un challenger Dixon–Coles para bajas anotaciones se evaluará después, no se incorporará por reputación o por observar un solo fallo. Referencias de investigación: [Dixon y Coles, registro de publicación de los autores](https://research-information.bris.ac.uk/en/publications/modelling-association-football-scores-and-inefficiencies-in-the-f/) y [extensión que describe la corrección de bajas anotaciones](https://arxiv.org/abs/2307.02139). El proyecto solo tomará la parte deportiva del modelado, sin cuotas como entrada.

## Evaluación y calibración

- **Referencias obligatorias:** frecuencias 1X2 de entrenamiento, localía simple y un Elo con tratamiento del empate explícito si se incluye como benchmark. No convertir un Elo binario en 1X2 repartiendo una probabilidad de empate arbitraria.
- **Partición inicial propuesta:** 2021–22/2022–23 para entrenamiento, 2023–24 para elegir regularización/calibración y 2024–25/2025–26 como dos periodos de evaluación. Si no hay datos completos, se rediseña el experimento antes de entrenar; no se rellena el holdout con datos elegidos por conveniencia.
- Congelar hiperparámetros y política de actualización antes del primer holdout. Si se actualizan fuerzas con partidos anteriores durante una simulación cronológica, esa regla debe estar predefinida y cada pronóstico debe conservar su cutoff; no se ajustan decisiones mirando el resultado global del holdout.
- Medir Brier multiclase y log loss, calibración para local/empate/visitante, estabilidad por temporada, inicio/fin de temporada y equipos ascendidos. Declarar si el Brier es suma o media de clases y mantener la misma convención en todas las comparaciones.
- Evaluar diferencias emparejadas sobre los mismos encuentros, con incertidumbre por bloques de jornadas/semanas. Informar tamaño de muestra y limitaciones de dependencia por equipos.
- El acierto bruto queda como dato secundario. No seleccionar el modelo solo porque acierta al favorito con más frecuencia, ni afirmar rentabilidad sin una evaluación separada de precios y costes.
- Si se calibra, hacerlo únicamente sobre validación, preservando la suma 1X2; la calibración no se vuelve a ajustar con el conjunto de evaluación.

## Pasos y entregables

| Paso | Entregable | Criterio de aceptación |
|---|---|---|
| 1. Definir alcance y datos | Liga, mercado 90 minutos, fuentes, esquema y política de aplazamientos | Identidad, estado, timestamps y licencia trazables; ningún precio en el esquema de variables |
| 2. Construir el histórico | Colector, normalizador y manifiesto de integridad por temporada | Cobertura contrastada, sin duplicados y marcadores finales válidos; excepciones explícitas |
| 3. Implementar baselines | Frecuencias/localía y Poisson regularizado | Probabilidades 1X2 válidas, partidos futuros sin marcador, reproducibilidad y tests temporales |
| 4. Ejecutar backtest | Reporte cronológico por temporada y contra referencias | Sin fuga; hiperparámetros congelados; Brier/log loss e incertidumbre sobre idénticos partidos |
| 5. Probar challenger | Dixon–Coles como experimento separado | Aporta mejora estable frente al Poisson base; si no, se conserva el base |
| 6. Seguimiento pregame | Captura diaria firmada y post mortem automático | Predicción guardada antes del inicio, liquidación a 90 minutos, reintentos y revisión de correcciones |
| 7. Integrar en PULSO | Panel de fútbol y ejecución protegida propia | Fecha coherente en calendario/pronóstico/botón; estados sin datos claros; publicación sin secretos |

## Estructura de implementación propuesta

Crear `soccer/sources.py`, `soccer/normalize.py`, `soccer/poisson.py`, `soccer/backtest.py`, `soccer/pregame.py`, `soccer/postmortem.py` y `soccer/tests/`. Los nombres son una propuesta; todavía no existen esos módulos. Reutilizar contratos de procedencia y registro, ampliando el adaptador para fútbol sin mezclarlo con coeficientes NHL/NBA/NFL.

Separar PRs: (A) datos y cobertura; (B) referencias y Poisson; (C) evaluación y candidato; (D) operación pregame/post mortem; (E) panel y ruta protegida. Así se puede rechazar una mejora estadística sin deshacer una mejora de datos.

## Criterios para publicar

Primero publicar, si corresponde, un **modelo base experimental** con alcance y limitaciones visibles. Una promoción posterior exige fuentes temporalmente válidas, versiones reproducibles, prueba frente al baseline fuerte, calibración por clase, mejora con incertidumbre documentada, seguimiento posterior intacto y revisión independiente. El tamaño de muestra y el umbral de mejora se fijan antes de evaluar; una fecha de entrega o una jornada acertada no certifica el modelo.

**Primer trabajo recomendado:** auditar cobertura de una liga en las cinco temporadas propuestas y reparar la persistencia del calendario compartido. Ese paso decide si los siguientes experimentos pueden ejecutarse con fundamento. No hace falta esperar a tener xG o alineaciones para evaluar un primer baseline de resultados.
