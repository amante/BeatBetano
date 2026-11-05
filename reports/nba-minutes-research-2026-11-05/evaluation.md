# NBA — modelo experimental de minutos si participa

**Evaluación retrospectiva. No es una rotación completa ni modifica ML.**

| Referencia | Apariciones de prueba | MAE (minutos) | RMSE (minutos) | Sesgo |
|---|---:|---:|---:|---:|
| last_five_mean | 612 | 4.7682 | 6.4062 | -0.8314 |
| last_appearance | 612 | 5.4428 | 7.2135 | -0.1683 |
| ridge_candidate | 612 | 4.7014 | 6.1057 | 0.0396 |

Filas por corte: {'train': 273, 'validation': 280, 'test': 612}. Partidos: {'train': 19, 'validation': 15, 'test': 31}. Lambda seleccionado sólo en validación: 10.

Mejora positiva favorece candidato frente a media de cinco apariciones.
IC95 de mejora MAE: [-0.12337790116880071, 0.266049075734576]
IC95 de mejora RMSE: [0.012751167072368653, 0.6336460810893292]

One early-season retrospective sample; source was collected after the historical games.
Historical availability time is approximated by a conservative six-hour post-tip delay, not original publication timestamps.
Only recorded appearances are scored; DNP, unseen roster members and playing probability are not modeled.
No current-game starters, minutes or appearance flags enter feature construction.
Reported total-game minutes include overtime; no regulation 240-minute allocation is claimed.
Whole-game bootstrap approximates dependence; repeated-player/team dependence across games remains.
No injury, replacement, position-feasibility, ML or +20 effect is inferred.
