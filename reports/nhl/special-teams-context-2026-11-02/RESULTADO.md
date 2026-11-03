# PP/PK y calendario: entradas reales conectadas, efectos aún no ajustados

## Comprobación de fuentes

Reproducción de los cuatro encuentros del 2 de noviembre de 2026:

- Ocho equipos con conteos completos PP y PK: goles/oportunidades, goles recibidos
  en inferioridad e inferioridades. Cero identidades sin resolver y cero errores.
- Los conteos llegan a las señales cuantitativas existentes en los ocho lados,
  junto con los ocho historiales de arquero reparados por el PR anterior.
- Ocho lados con contexto del calendario oficial: encuentro anterior, horas entre
  inicios, B2B según fecha oficial NHL y cambio de recinto. Ninguno tiene B2B en esta
  captura. Los JSON adjuntos conservan fuentes, huellas y horas de recuperación.

| Equipo | Horas entre inicios programados | Cambio de recinto |
|---|---:|---|
| BOS | 55 | No |
| VGK | 74 | Sí |
| FLA | 73 | No |
| DET | 55 | Sí |
| CHI | 56 | Sí |
| COL | 47 | Sí |
| SJS | 54 | No |
| CGY | 48 | Sí |

Las horas NO son descanso desde la bocina final. No se calculan kilómetros ni rutas
sin fuentes verificadas. Un encuentro anterior aún futuro no acredita carga real;
ese contexto queda marcado como planificado. Si cambia la identidad/hora oficial del
partido, se bloquea esa entrada.

## Cortes temporales

PP/PK usa un filtro explícito de temporada, fase regular y gameDate hasta el día
anterior a la captura. Antes de consultar estadísticas se verifica en el marcador
oficial que ese día no tenga juegos en vivo o pendientes sin posponer/cancelar.
No se usan estadísticas totales actuales como si hubieran existido antes.

Se guardan las respuestas originales comprimidas en el artifact de cada ejecución.
Si falla una fuente, se mantiene el faltante: no se reemplaza por una media inventada
ni por la temporada completa sin corte. La hora común de análisis se fija después
de obtener contexto, PP/PK y forma. La captura de standings también conserva su hora
real de recuperación, separada del timestamp inicial del reporte.

## Lo que este PR no acredita

Conectar conteos permite calcular tasas observadas e indicadores descriptivos. No
ajusta coeficientes de PP/PK, descanso ni viajes, no certifica causalidad, no reemplaza
el baseline y no completa los trece módulos. La contribución al ML sigue nula hasta
una comparación temporal documentada. El núcleo registra el contexto observado,
con sus limitaciones, en vez de declarar que no recibió información alguna.
