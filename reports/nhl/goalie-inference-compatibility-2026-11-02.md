# Compatibilidad e integración de inferencia ML de arquero

Se descargó y examinó el artefacto real del workflow #269, ejecución 41261897801,
artifact 13064714085. Contiene pesos y calibrador ajustados: 1.531 juegos de ajuste,
557 de validación y 524 de prueba; corte de ajuste 2025-11-28 y validación 2026-03-02.
La existencia de esos parámetros no demuestra compatibilidad con la captura actual.

Sus cuatro variables son SV% de cada arquero e indicador histórico de fuerza de cada
equipo. El constructor #267 acumula registros por jugador/equipo en la colección
histórica y usa titulares identificados retrospectivamente. La captura #251 contiene
estadísticas de temporada y arqueros observados por proveedor. No hay una equivalencia
verificada que autorice sustituir una variable por otra con el mismo nombre.

Por eso el PR no instala esos pesos como candidato live. Conecta en cambio el
contrato prospectivo #291 (baseline-logit + diferencia de SV% de temporada) desde
su evaluación ajustada hasta la inferencia por partido. Incluye modelo de control
recalibrado, validación dimensional/integridad y persistencia de cada inferencia.
Una prueba con parámetros APRENDIDOS de datos sintéticos verifica sensibilidad al
arquero; esos pesos son exclusivos del test y no se publican como parámetros NHL.

El nuevo resultado permite comparar baseline/candidato/deltas cuando se disponga de
un artefacto válido. De lo contrario deja `goalie_model_not_executed`, motivos y
probabilidades/deltas nulos. Es un resultado de diagnóstico, no una ejecución de un
modelo deportivo completada. El baseline y sus cinco mercados conservan su origen.

Pendiente de evidencia: ajustar/evaluar el candidato con suficiente información
prospectiva y protocolo congelado; revisar sus resultados frente al baseline y la
recalibración. No hay un nuevo porcentaje NHL válido que publicar hoy por el mero
hecho de conectar el adaptador.
