# Post mortem NHL — 1 de noviembre de 2026

Generado: 2026-11-02T10:14:11.902632+00:00. Código/fuentes de pronóstico: `22007939de94a4c397e92394bc6b0e328d8042b9`.

## Resultado ejecutivo

Se liquidaron los cinco encuentros con resultados oficiales y secuencias de goles. Se puntuaron 25 predicciones originales: cinco mercados por partido. Los 180 archivos encontrados contienen repeticiones de ejecuciones; se excluyeron 155 emisiones repetidas. La política, fijada antes de observar los aciertos, es conservar la primera emisión válida por partido/modelo/mercado.

El modelo evaluado es `outcome-only-206-frozen-params`: experimental, basado en resultados históricos; no es el motor completo de plantillas y arqueros. No se modificaron parámetros ni se promovió ningún modelo.

## Partido por partido

El “favorito ML” es la clase de mayor probabilidad; no es una recomendación de apuesta.

| Partido | Resultado visitante–local | Favorito ML original | Probabilidad | ML | Primero en +3 | Local +3 / visitante +3 |
|---|---|---|---:|---|---|---|
| WPG — CAR | 0–7 | CAR | 57.7% | Acierto | CAR | Sí / No |
| MIN — WSH | 5–1 | WSH | 54.2% | Fallo | MIN | No / Sí |
| UTA — PHI | 3–6 | PHI | 51.2% | Acierto | PHI | Sí / No |
| EDM — NYR | 4–1 | EDM | 50.5% | Acierto | EDM | No / Sí |
| OTT — ANA | 3–6 | ANA | 53.5% | Acierto | OTT | Sí / Sí |

## Métricas de esta jornada

Brier y log loss evalúan las probabilidades: menor es mejor. La cifra de aciertos usa la clase más probable y es secundaria. El Brier multiclase se promedia entre clases; no se comparan valores absolutos entre mercados de distinta dimensión.

| Mercado | Partidos | Aciertos de la clase más probable | Brier | Log loss |
|---|---:|---:|---:|---:|
| Ganador, incluidos desempates | 5 | 4/5 | 0.234159 | 0.661265 |
| Resultado en tiempo regular | 5 | 4/5 | 0.184662 | 0.919927 |
| Local alcanza ventaja +3 | 5 | 2/5 | 0.369787 | 0.970408 |
| Visitante alcanza ventaja +3 | 5 | 2/5 | 0.373836 | 0.977554 |
| Primero en alcanzar +3 | 5 | 0/5 | 0.296001 | 1.399778 |

Solo hay cinco partidos independientes; los 25 mercados están correlacionados. Un 80% de acierto ML en esta fecha no demuestra precisión futura, calibración ni rentabilidad.

## Comparación ML con el challenger

Solo cuatro partidos tienen baseline y challenger emparejables; CAR–WPG no tiene challenger pregame válido en la cohorte seleccionada. En esos cuatro encuentros: baseline Brier 0,248002 / log loss 0,689173; challenger Brier 0,264724 / log loss 0,723135. El challenger resulta peor en ambos indicadores en esta muestra; no se promueve. No se compara su cifra de cuatro partidos con el baseline agregado de cinco.

## Aprendizaje registrado

1. **Tres objetivos distintos.** En OTT–ANA, Ottawa fue primero en +3; ambos equipos alcanzaron +3; Anaheim ganó 6–3. La secuencia real de goles importa: el margen final no basta para identificar quién alcanzó primero +3 ni para negar una ventaja anterior del perdedor. Es un caso de regresión permanente; la definición vigente de los objetivos ya permite este resultado.
2. **Señal a investigar en +3.** Los cinco partidos tuvieron una ventaja +3. El modelo esperaba aproximadamente 2,44 partidos con alguna ventaja +3 y eligió “ninguno” como clase más probable en los cinco. Se registra una hipótesis de infrapredicción en esta jornada; no una conclusión general ni una autorización de subir probabilidades. Hay que medirlo por semanas, tasas base, estado del marcador y segmentos en una muestra independiente.
3. **Emisiones repetidas.** Una misma predicción ejecutada varias veces no equivale a evidencia independiente. Las evaluaciones deben mantener la política de emisión original; una política de última actualización pregame exige una comparación separada y predefinida.
4. **No inventar explicaciones causales.** Esta auditoría no atribuye los fallos a un arquero, lesión o alineación sin una captura pregame verificada de esos factores. El baseline actual no los modela.

## Qué se guardó y cómo entra al proceso del modelo

- `postmortem.json`: métricas, detalle de 25 mercados, comparación emparejada, fuentes y hashes.
- `selected-frozen-forecasts.json`: copias exactas de las emisiones originales seleccionadas y sus rutas.
- `learning-observations.json`: cinco observaciones postgame, fecha de disponibilidad y tres hipótesis de investigación. Quedan separadas de las variables pregame y en cuarentena para un futuro entrenamiento cronológico.
- `evidence/*.json.gz`: respuestas oficiales originales comprimidas, con SHA-256 de los bytes originales y del archivo comprimido.
- `reproduce.py`: reconstrucción y evaluación reproducible con los validadores existentes.

**Estado del aprendizaje:** guardado como datos y decisiones de investigación; no aplicado a los pesos del modelo en vivo. Antes de incorporarlo a un nuevo entrenamiento, debe verificarse el corte temporal, mantener un conjunto de evaluación intacto y comparar la nueva versión con el baseline congelado. Este día ya observado no puede reutilizarse como holdout intacto de una mejora inspirada en él.

Para reproducir, descomprimir las respuestas guardadas en una carpeta y ejecutar `python reproduce.py --repo CHECKOUT --raw RESPUESTAS --out NUEVA_SALIDA`. El checkout debe corresponder a la revisión indicada; la salida conserva el detalle de cada pronóstico. Se ejecutaron 22 pruebas de los reconstructores, scoring y comparación existentes, todas correctas.

## Fuentes oficiales

- https://api-web.nhle.com/v1/gamecenter/2026020227/play-by-play
- https://api-web.nhle.com/v1/gamecenter/2026020228/play-by-play
- https://api-web.nhle.com/v1/gamecenter/2026020229/play-by-play
- https://api-web.nhle.com/v1/gamecenter/2026020230/play-by-play
- https://api-web.nhle.com/v1/gamecenter/2026020231/play-by-play
- https://api-web.nhle.com/v1/score/2026-11-01
