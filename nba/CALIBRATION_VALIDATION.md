# NBA: calibración, incertidumbre e independencia

`calibration_validation.py` reproduce 2.460 predicciones retrospectivas: temporada
final 2024 para inicializar; finales 2025 y 2026 para puntuar Elo y Challenger.
Valida el ledger completo (3 × 1.230; 30 × 82), orden e identidades. Las mismas
filas alimentan ambos modelos. No usa cuotas ni ajusta coeficientes.

## Resultado de la evaluación congelada

| Temporada final | Mejora Brier Challenger | IC95 por semanas | Mejora log loss | IC95 por semanas |
|---|---:|---|---:|---|
| 2025 | 0,002403 | [0,000633; 0,004242] | 0,005140 | [0,001203; 0,009345] |
| 2026 | 0,002936 | [0,000303; 0,005597] | 0,006221 | [-0,000198; 0,012487] |
| Ambas | 0,002670 | [0,001013; 0,004222] | 0,005681 | [0,001808; 0,009348] |

Mejora = pérdida Elo menos pérdida Challenger. Los resultados favorecen al
Challenger en promedio, pero el intervalo de log loss de 2026 incluye cero.
No son intervalos corregidos por selección de modelos.

ECE de 10 intervalos: Elo/Challenger = 0,036882/0,038015 en 2025;
0,027688/0,040327 en 2026; 0,032285/0,032688 en ambas. Por esta medida,
Challenger no mejora la calibración respecto de Elo. Su sesgo medio conjunto
es +0,028306: sobrestima en promedio la victoria local en 2,83 puntos
porcentuales. Esto es un diagnóstico histórico, no una corrección a aplicar
a las probabilidades de hoy.

## Método y límites

- Brier, log loss, acierto, sesgo medio y bins de fiabilidad de anchura fija 0,1.
- Wilson 95% de frecuencia observada en cada bin. Son intervalos descriptivos
  bajo independencia Bernoulli, no intervalos corregidos por dependencia NBA.
- Bootstrap emparejado de pérdidas: 2.000 réplicas, semilla 20261104. Se
  remuestrean semanas ISO completas dentro de cada temporada, conservando juntos
  los partidos de la semana y la pareja de predicciones. Cada media se pondera
  por número de partidos efectivamente remuestreados. Sensibilidad por día
  NBA (America/New_York) disponible en el JSON.
- Las semanas aproximan la dependencia de calendario. No resuelven dependencia
  persistente de equipos ni correlación entre temporadas. Dos temporadas no
  bastan para estimar con precisión la variabilidad entre temporadas futuras.
- No se eligen bins, umbrales, pesos ni versiones usando estas cifras. No hay
  umbral automático de certificación por ECE ni promoción por CI positivo.

La auditoría de independencia está en
`reports/nba-validation-2026-11-04/independence-audit.md`. Las reglas del híbrido
son explícitamente post-hoc; para los coeficientes originales no se encontró
registro previo suficiente. Por eso todo este resultado es retrospectivo.

## Reproducción

```
python nba/calibration_validation.py \
  --history reports/nba-2026-11-04/history.json \
  --output /tmp/nba-calibration.json --summary /tmp/nba-calibration.md
python -m unittest discover -s nba/tests -v
```

Los archivos de salida son de creación exclusiva. Los hashes identifican los
inputs y las filas evaluadas; exp/pow pueden variar una ULP entre macOS y Linux.
Las pruebas comparan resultados numéricos con tolerancia absoluta 1e-12, sin
modificar las capturas originales. El protocolo prospectivo de esta evaluación
registra hashes del código y un corte futuro; no declara que ya exista cobertura
de emisiones suficiente ni que un workflow de tests equivalga a certificación.
