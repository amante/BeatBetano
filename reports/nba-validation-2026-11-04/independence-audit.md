# Independencia del backtest: auditoría de procedencia

Revisión del 4 de noviembre de 2026. Evidencia del historial Git y de los módulos;
no se presume disponer de registros de investigación externos al repositorio.

| Componente | Evidencia encontrada | Conclusión |
|---|---|---|
| Elo | Benchmark de coeficientes fijos; recorrido por resultados anteriores | Sin uso del resultado del partido evaluado en su propia predicción. No se acreditó un protocolo de selección registrado antes de conocer los resultados históricos. |
| Challenger margen/descanso | Primer commit `09b7f3337cc2b2b53daee86a6d1a3b7450c198db`, 23-oct-2026 20:27:50 -03; coeficientes 0,025 y 0,035 declarados hipótesis | Las temporadas 2024–25/2025–26 ya habían terminado al incorporar el modelo al repositorio. Su recorrido cronológico es válido como evaluación retrospectiva; no acredita por sí mismo independencia de la selección. No se encontró evidencia suficiente para afirmar que esos coeficientes se eligieron con los resultados del test, ni para certificar lo contrario. |
| Híbrido | Commit `9402eb86fcf0757c7c1570e05e9ad30676496fdb`, 23-oct-2026 20:41:28 -03. `nba/guardrails.py` declara reglas post-hoc motivadas por inspección de segmentos de 2024–25/2025–26 | Esas temporadas NO constituyen validación independiente del híbrido. |
| Sensibilidad y ablaciones | `nba/hybrid_gate_audit.py` inspecciona umbrales 0/1/2/3/5, con `independent_holdout_passed=False`; `ed7c33304362132b8c23e9c430bdbb692141d357` habilita ablaciones sin cambiar valores por defecto | Sirven para diagnóstico, no para seleccionar un ganador y validarlo usando los mismos partidos. |

Conclusión: **no se certifica validación independiente de ningún modelo**.
Esto no anula las métricas retrospectivas. La incertidumbre por bootstrap tampoco
corrige selección post-hoc ni demuestra que una temporada sea intocada.

El informe principal evalúa Elo y Challenger sin sus reglas de híbrido; no ajusta
coeficientes ni calibra probabilidades sobre los mismos juegos que se puntúan.
Las estadísticas históricas fueron recuperadas posteriormente; no son archivos
del estado exacto de la fuente antes de cada partido, aunque el recorrido sólo
incorpora resultados de juegos anteriores.
