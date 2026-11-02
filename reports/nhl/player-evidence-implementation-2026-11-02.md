# Primera conexión de evidencia deportiva NHL — 2 noviembre 2026

## Entregado

Se extiende el colector existente, sin crear otro modelo. Las capturas de artículo y
ESPN se conservan; las líneas/bajas se reconcilian con plantillas oficiales por ID y
posición. Se conectan las observaciones de arquero ya reconciliadas y los indicadores
previos del módulo #251. El workflow congela la evidencia antes de emitir pronósticos
y la guarda por ejecución en Git y como artifact.

## Comprobación real

Consulta de fuentes públicas NHL/ESPN para los cuatro partidos del 2 de noviembre:
cuatro encuentros; ocho equipos con los 18 IDs de sus líneas proyectadas resueltos;
ocho identidades de arquero vinculadas con historial previo; ningún nombre de lesión
sin resolver en esta captura. Esto comprueba conexión de datos, no confirmación de
titulares ni precisión predictiva. No se ejecutó una simulación ni se modificaron
probabilidades para realizar la comprobación.

La API oficial de plantillas redirige `/current` a la temporada; la comprobación
siguió esa redirección pública, como hace urllib en el colector existente.

## Pendiente antes de cambiar probabilidades

1. Unir capturas a resultados y baseline por emisión/ID, comprobando cortes temporales.
2. Congelar el protocolo de variables, penalización y validación cronológica.
3. Entrenar/evaluar primero arquero, luego bajas y líneas por separado, frente al
   baseline fuerte en los mismos partidos; conservar tasas y tamaños de muestra.
4. Publicar calibración, incertidumbre y limitaciones; seguir en sombra si no mejora.

No se usan listas actuales para reconstruir alineaciones históricas. No se afirma
que ocho equipos en un día constituyan una muestra de entrenamiento suficiente.
