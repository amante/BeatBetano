# Prueba real de predicciones progresivas — 6 de noviembre de 2026

**Resultado: archivo inicial + actualización verificados para 12 partidos reales,
sin publicación en producción.** No es una prueba de precisión ni calibración.

La versión fusionada del PR #345 se probó en una rama independiente. Se hicieron
dos consultas nuevas a los calendarios y dos ejecuciones reales de los modelos,
reutilizando el mismo directorio de revisiones y los datos históricos en caché.
No se cambiaron alineaciones, lesiones, probabilidades ni horas para provocar
un resultado artificial.

| Comprobación | Resultado |
|---|---|
| Primera captura / segunda captura | 33 encuentros cada una; cero errores de consulta |
| Partidos pendientes en la captura chilena | 7 NBA, 3 NHL, 5 fútbol |
| Pronósticos iniciales archivados | 9 NBA + 3 NHL |
| Actualizaciones reales archivadas | 9 NBA + 3 NHL |
| Archivos de predicción finales | 24: dos versiones por partido |
| Primeros archivos conservados sin cambios | 12/12, comparados byte a byte por SHA256 |
| Cadenas, versiones y vínculos verificados | 12/12 |
| Emisiones anteriores al inicio | 24/24 |
| Primera emisión | 11:57 del 6 de noviembre, hora de Chile |
| Segunda emisión | 12:00 del 6 de noviembre, hora de Chile |
| Partidos con cambio numérico de probabilidad | 0/12 |

La base NBA consulta una fecha de liga estadounidense completa; sus nueve partidos
incluyen dos que empiezan a medianoche del día siguiente en Chile. Por
eso son nueve pronósticos en el archivo, aunque la captura del día chileno tenga
siete pendientes. No se suman como dos partidos adicionales del día chileno.
NBA publica aquí la base Elo disponible; NHL la base estadística exploratoria.
No se afirma haber validado todo el Challenger ni probabilidades +20/3GLP.

Las probabilidades no cambiaron porque las nuevas consultas no cambiaron las
características utilizadas por estas bases. Sí avanzaron los cortes y emisiones,
la etapa pasó de `initial` a `update` y se conservaron los supuestos pendientes.
Un resultado idéntico es una actualización legítima, no un error. Este intento no
prueba todavía el comportamiento frente a una noticia material de última hora.

## Problema real detectado y corregido

El informe inicial marcó cobertura NHL 0/3 porque comparaba los identificadores
de ESPN con los oficiales NHL. Los tres pronósticos ya estaban generados y no
se alteraron. La corrección exige una correspondencia única entre equipos locales
y visitantes mediante la tabla explícita ya existente de franquicias, además de
la misma hora de inicio. No hace coincidencias aproximadas ni cambia IDs del
archivo de predicciones. Una hora distinta, equipos invertidos o dos candidatos
compatibles dejan la vinculación sin resolver.

`first-run.json` permanece intacto como evidencia del problema. La derivación
`first-run-nhl-coverage-correction.json` muestra los tres vínculos comprobados;
`second-run.json` ya reconoce cobertura NHL 3/3. Se añadieron pruebas de regresión:
53 pruebas multisport aprobadas.

También se comprobó la persistencia prevista para producción: la regla general
`data/` de `.gitignore` ocultaba `frontend/data/forecast_archive` a Git. Se añadió
una excepción explícita para `frontend/data/`; los datos de trabajo privados en
la carpeta raíz `data/` siguen ignorados. Esto permite al flujo conservar los
archivos publicados sin forzar la inclusión de otros datos. La prueba de inclusión
se hizo sobre la ruta real prevista, sin publicar esos archivos en producción.

## Cobertura que sigue faltando

- NFL y tenis: no había encuentros pendientes en la captura. No se probaron sus
  pronósticos en vivo en este intento; tenis continúa sin modelo numérico.
- Fútbol: cuatro encuentros son de ligas sin modelo compatible. El encuentro de
  Premier League es Everton–Coventry City; Coventry no está en las identidades
  históricas del modelo actual. Los cinco quedan sin probabilidad explícita,
  sin completar valores por semejanza de nombres o con cifras inventadas.
- Titulares, bajas y demás supuestos no verificados siguen visibles. No se
  certifican selecciones, aciertos, rentabilidad ni calibración con esta prueba.
- El dashboard todavía debe mostrar las predicciones y sus revisiones. Estos
  resultados están guardados como evidencia, no desplegados en producción.

## Evidencia y reproducción sin red

`fixtures-first.json` y `fixtures-second.json` contienen las capturas deportivas;
`model-work/` conserva salidas e historial usado; `archive/` conserva las dos
versiones selladas por partido. `live-verification.json` incluye probabilidades,
diferencias, cortes, emisiones y hashes por encuentro. El manifiesto inicial
permite comprobar que ningún primer pronóstico se reescribió.

```sh
python reports/live-forecast-pilot-2026-11-06/verify_pilot.py
python -m unittest discover -s multisport/tests -q
```

El verificador reabre los archivos existentes, comprueba sus sellos, la cadena de
revisiones y las emisiones pregame, y compara sus resultados con la verificación
archivada. No vuelve a calcular ni sustituye pronósticos históricos.
