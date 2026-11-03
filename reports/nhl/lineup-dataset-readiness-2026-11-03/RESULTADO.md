# Conjunto de evaluación de bajas y líneas: primera comprobación completa

Jornada 2026-11-03. Esta es una verificación local con fuentes reales; el ID local no corresponde a una ejecución de GitHub Actions. No se generaron pronósticos nuevos.

- 11 registros congelados antes de los encuentros.
- 0 registros completos; 11 descartados por entradas incompletas.
- 0 ejemplos etiquetados disponibles para entrenar.
- Las proyecciones oficiales consultadas siguen modificadas el 2026-11-02 a las 19:19 UTC; no acreditan líneas de la jornada del 3.
- La cadena conserva 494 historiales individuales y un error de conteos; 22 referencias de participación. Se reutiliza la captura real previa con sus horas originales; solo se recuperaron de nuevo las referencias. No se retrofecharon las fuentes.

## Reproducción

Desde el repositorio: `python -m nhl.lineup_outcome_dataset --output /tmp/lineup-cohort.json`. El registro permanente está en nhl/learning/lineups/local-20261103051535.json; su bundle conserva respuestas de historial y referencia. La evidencia de proyección, el HTML editorial y las identidades están en projection-sources.json.gz, con SHA-256 separado. Los valores del bundle se decodifican desde hexadecimal.

## Decisión

No entrenar con este conjunto vacío ni sustituir las proyecciones por los participantes conocidos después del resultado. El primer hito sigue abierto hasta una captura con líneas vigentes e historiales completos; luego se necesitan suficientes partidos con resultados y separación temporal para comparar con el baseline. Este PR verifica la cadena, no acredita que el conjunto esté listo ni una mejora predictiva.
