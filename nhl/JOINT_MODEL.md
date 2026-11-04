# NHL: modelo deportivo conjunto en implementación

El pronóstico publicado continúa siendo histórico. El escenario de minutos es una sensibilidad separada. El nuevo `joint_goal_model.py` no se conecta a producción hasta contar con parámetros ajustados y evaluación temporal.

El motor usa un único proceso de goles de regulación por lado. Sus entradas explícitas son tasas por 60 de goles, asistencias, tiros y PIM de los jugadores bajo el despliegue previsto; tiros permitidos por la defensa rival; save% del arquero rival identificado; PP propio, PK rival, oportunidades PP estimadas y continuidad de líneas. Todos los campos entran al predictor. Sus coeficientes se estiman juntos, no se fijan manualmente ni se obliga a que sean distintos de cero. En particular, asistencias y goles no se suman como eventos independientes.

Ganador y tiempo regular derivan del mismo proceso Poisson; el desempate se reparte 50/50 como supuesto provisional. Esto NO completa el modelo de trayectoria +3, ni incorpora todavía calidad de tiro o química no observada. No se presentan como calibrados.

Faltan productores verificables para defensa individual y por unidad, despliegue por situación, oportunidades PP condicionadas al rival y referencia de plantilla sana/esperada. La ausencia prolongada no se corrige usando de nuevo solo el partido anterior. PIM no reemplaza conteos de penalidades menores, mayores, coincidentes y oportunidades efectivas.

Entrenamiento: solo observaciones con reloj previo al inicio, IDs únicos por partido/equipo y objetivos separados de goles de regulación. Sin datos reales completos no se entrena; sin variación de una variable no se estima su efecto. Las pruebas de sensibilidad usan parámetros sintéticos exclusivamente para comprobar conexión y no son evidencia de acierto ni parámetros publicables.

Aceptación para producción: construir datos históricos con fuentes anteriores al inicio, ajustar exclusivamente en entrenamiento, medir en fechas posteriores contra el histórico y el escenario de minutos, revisar calibración y contribución por ablación. Mantener todas las emisiones originales y evaluar el pronóstico conjunto en el post mortem. Hasta entonces, nunca cambiar etiquetas de cobertura a "aplicado" por tener un campo conectado.
