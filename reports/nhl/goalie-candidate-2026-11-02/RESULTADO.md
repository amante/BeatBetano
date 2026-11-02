# Candidato numérico de arquero: ajustado, evaluado y no aprobado

Se reconstruyeron 2.811 partidos oficiales y las apariciones de TODOS los arqueros,
incluidos relevos. Las tasas se reinician al cambiar de temporada y cada fila usa
solo fechas anteriores al partido. Nunca se añade el boxscore del propio encuentro
antes de emitir sus variables. Los identificadores de titulares históricos son
observaciones postgame: este es un experimento condicional retrospectivo, no una
prueba de que la alineación hubiese estado confirmada antes de jugar.

Quedaron 1.342 juegos de entrenamiento, 550 de validación y 429 de prueba. Se mantiene
el mismo baseline en las tres comparaciones; la penalización se eligió solo con la
validación, entre 0.005/0.02/0.1. Los cortes son 2025-11-28 / 2026-03-02 / 2026-10-26.
La historia ya había sido explorada por trabajos anteriores: no se llama evaluación
independiente nueva. Los archivos originales, código y parámetros están conservados.

| Modelo, mismos 429 partidos | Brier | Log loss |
|---|---:|---:|
| Baseline publicado reconstruido temporalmente | 0.245599 | 0.684300 |
| Recalibración sin arquero | 0.245171 | 0.683428 |
| Recalibración + diferencia de SV% de arquero | 0.246198 | 0.685515 |

Menor es mejor. El candidato con arquero no mejoró ninguno de los dos controles.
Se conservan sus coeficientes en `research-parameters.json`, FUERA de la ruta de
parámetros desplegados. La decisión registrada es `not_approved_no_incremental_gain`.
PULSO debe explicar ese motivo en lugar de simular un ajuste cero o afirmar que no
se ha realizado ninguna evaluación. Este PR no reemplaza el baseline ni activa
porcentajes del candidato rechazado.

Esto no demuestra que el arquero carezca de impacto. Demuestra que esta definición
de SV% de temporada y este ajuste no añaden mejora en esta muestra. Calidad de tiros,
defensa, selección de titulares y cambios de contexto siguen siendo limitaciones.
Los cruces de arqueros potenciales siguen preservados con sus propios estados;
conservarlos no autoriza atribuirles porcentajes de un modelo no aprobado.

## Reproducir

Desde la raíz del repositorio, con Python 3.9+:

```sh
python -m nhl.goalie_historical_candidate \
  --labels reports/nhl/goalie-candidate-2026-11-02/evidence/labels.csv \
  --manifest reports/nhl/goalie-candidate-2026-11-02/evidence/labels-manifest.json \
  --cache-zip reports/nhl/goalie-candidate-2026-11-02/evidence/historical-cache.zip \
  --report-output /tmp/nueva-evaluacion.json \
  --model-output /tmp/nuevos-parametros.json
```

Las salidas son de creación exclusiva. CI reconstruye las tasas, reajusta y compara
métricas y coeficientes contra la versión guardada. Los mínimos de muestras son
controles operativos, no una certificación de potencia estadística o validez.
