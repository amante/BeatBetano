# NHL — ejecución de la recuperación de 13 módulos

## Primera entrega comprobada

Reproducción sobre los archivos de la ejecución real 41533924732:

| Comprobación | Antes | Con la corrección |
|---|---:|---:|
| Identidades de arquero enlazadas al puente | 0/8 | 8/8 |
| Señales cuantitativas de arquero alimentadas | 0/8 | 8/8 |
| Combinaciones de candidatos | 5 | 16 (4 por partido) |
| Nombres de candidato sin resolver | — | 0 |

Se corrigen ID, corte temporal y paquetes vacíos; se preservan todos los candidatos.
Las cifras son cobertura de una reproducción, no métricas de acierto ni nuevos
porcentajes NHL. Las pruebas numéricas de sensibilidad usan modelos ajustados solo
en fixtures sintéticos; esos parámetros no se publican.

## Entregables y dependencias restantes

| Módulo | Entregable concreto | Aceptación antes de aplicar un efecto |
|---|---|---|
| CRS | Plantilla por ID y valoración previa de cada jugador | Fuente temporal, historial y valoración evaluada; no sumar nombres como rating |
| Bajas/reemplazos | Diferencia entre alineación de referencia y esperada | Ausencias, reemplazos, minutos e incertidumbre; validación incremental |
| Unidades ofensivas | Rendimiento por línea y despliegue previsto | Historia/TOI previa, definición estable y evaluación frente al baseline |
| Unidades defensivas | Rendimiento de parejas y suplentes | Métricas/TOI, cobertura y contribución estimada |
| Arquero | Todos los candidatos y ML condicional por cruce | Contrato de variables compatible, parámetros ajustados, sensibilidad y evaluación temporal |
| PP/PK | Conteos de goles/oportunidades y matchup | Fuente fechada con denominadores, ajuste y evaluación |
| Localía/descanso/viajes | Historial de calendario, B2B, recinto y desplazamiento | Relojes y viajes verificables; efectos ajustados, sin duplicar localía del baseline |
| División/rivalidad | Registro y variable contextual definida | Ablación que demuestre aporte antes de asignarle un peso |
| Calidad/momentum | Fuerza y forma corregidas por rival | Historia previa y evaluación de estabilidad; no confundir goles por juego con fuerza ajustada |
| ML conjunto | Inferencia de módulos activos y trazabilidad de contribuciones | Mismos juegos para comparar, incertidumbre/calibración y estados parciales explícitos |
| Tiempo regular | Modelo de local/empate/visitante con variables deportivas | Entrenamiento y calibración de su propio objetivo |
| +3/primero en +3 | Modelo de trayectorias, ambos lados y ninguno | Etiquetas de secuencia auditadas y evaluación por mercado |
| Rescate/DUAL/FUERTE | Objetivos y dependencia conjunta; reglas congeladas | Probabilidades/umbrales evaluados, no productos de marginales por suposición |

Retorno de lesión y estilo rival se documentan como subexperimentos de disponibilidad,
calidad y matchup, no módulos completados por disponer de un archivo. Se conserva el
baseline como referencia estadística parcial. No se declara que los trece módulos
estén ajustados ni que una cantidad fija de partidos valide su contribución.

## Límites reales que no resuelve este PR

No existe todavía en el repositorio un artefacto ajustado compatible para producir
el nuevo ML de arquero. El modelo histórico #269 no comparte las mismas definiciones
con las capturas actuales. Tampoco hay historial pregame completo de lesiones/líneas
que permita certificar hoy sus efectos; las listas actuales no pueden reconstruirlo.
La próxima entrega numérica debe ajustar y evaluar un contrato explícito con datos
admisibles, conservando los bloqueos donde esa evidencia aún no exista.
