# Sports Model Validation Lab

Nuevo proyecto de calibración y backtesting deportivo para NHL, NFL, NBA, fútbol y tenis.

Este repositorio reemplaza la antigua aplicación BeatBetano. Conserva el nombre del repositorio, pero no utiliza ni despliega su aplicación React/Vite anterior.

## Estado
- MVP inicial de validación histórica en `validation/`.
- NFL: baseline Elo secuencial y métricas Brier, log loss y fiabilidad.
- NBA: detector de ventajas de 20 puntos basado en play-by-play.
- Los modelos oficiales 2026–27 y los challengers 2026–27.1 **no están aún implementados ni calibrados aquí**.
- No se usan cuotas de mercado para pronosticar.

## Comenzar
Ver [validation/README.md](validation/README.md).

## Principio de comparación
Nunca confundir el baseline reconstruido con los modelos oficiales históricos. Comparar únicamente tras disponer de las predicciones congeladas y de datos cronológicamente admisibles.
