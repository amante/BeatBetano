# Candidato ML de arquero — parámetros revisados antes de activar la comparación

El archivo opcional `goalie-ml-candidate.json` debe exportarse desde una evaluación
prospectiva #291 con `python -m nhl.goalie_ml_inference export --evaluation RUTA --output RUTA_NUEVA`.
El exportador comprueba contrato, dimensiones, muestras y cronología. La revisión
humana del protocolo/evidencia sigue siendo necesaria: las huellas comprueban
contenido, no acreditan por sí solas la validez independiente del experimento.

El contrato exige dos variables exactamente: logit del baseline de la misma emisión
y diferencia de saves/shots acumulados de temporada antes de la fecha UTC de captura,
con ambos arqueros confirmados por el proveedor e identificados por ID. Conserva por
separado el control de recalibración de una sola variable. Ni lesiones ni líneas ni
RT/+3 se ajustan por este candidato ML. No existe promoción automática del baseline.

No se incluye un archivo de parámetros ficticio ni una copia del modelo #269: usa
cuatro variables distintas y otro proceso de construcción histórica, sin paridad de
capturas pregame demostrada. La ausencia del artefacto es un estado normal y explícito
`missing_fitted_model`, con probabilidades y deltas nulos, no cero.

Una evaluación futura compatible se exporta a una ruta nueva y se propone en un PR
antes de guardarla aquí. Su `available_at_utc` debe preceder la emisión comparada.
Reejecutar después de un partido no puede fabricar una predicción pregame.

La evaluación histórica reproducible del 2 de noviembre está en
`reports/nhl/goalie-candidate-2026-11-02`. Reinicia tasas por temporada y reconstruye
apariciones previas; ajusta los dos parámetros deportivos/estadísticos y sus controles.
No mejoró al baseline/control, por lo que sus pesos se conservan para investigación y
NO se guardan en `goalie-ml-candidate.json`. `goalie-ml-assessment.json` comunica la
decisión real para que el frontend diga que el candidato evaluado no se aplica.
