# NHL integrated match engine — PR #320

## What the case proves

`joint_match_engine_320.py` runs one match from dated team, skater, lineup, special-team and goalie inputs through expected regulation goals into ML, regulation result, +3 lead and first-to-+3. Each possible goalie pair remains its own scenario. The inputs and reconstructed output for COL–CBJ are in `reports/nhl/integrated-case-COL-CBJ/`.

The 18 projected skaters are assigned exactly 180 forward and 120 defense skater-minutes per regulation game. Departures and returning projected players are reconciled within their position group. Each player's EV/PP/PK usage proportions redistribute that budget; goals, assists, shots and PIM are recalculated at that usage. The model reports individual and team changes. This prevents minutes from exceeding 300.

Player points by strength (goals plus assists) convert to team goal events through the actual current-roster points-per-goal ratio for that strength. This lets playmaking affect the scoring rate without counting assists as extra goals. Projected even-strength shots are compared with the opponent's team shots-against. PP opportunity volume uses both teams' observed PP/short-handed counts, adjusted by the projected opponent lineup's PIM rate relative to that team's roster history. PP conversion combines own team PP efficiency, projected PP-personnel scoring rate, and opponent PK allowance, with the PK rate shrunk halfway toward the games-weighted league rate. No PIM-minute-to-power-play conversion is hardcoded.

For each candidate goalie, its own observed saves/shots replaces the opponent team's historical goals-against-per-shot rate. The engine does not blend unconfirmed goalies or invent starter weights. The same regulation-goal Poisson distributions generate all displayed markets.

## Boundaries

The engine uses transparent structural rate calculations, not learned coefficients. It is not calibrated. Results are marked non-publishable until source coverage and prospective integration are complete. The included COL–CBJ rates are a reconstruction: full NHL Stats API skater/team extracts were retrieved at 00:50 UTC, after the 00:00 UTC scheduled start. They cannot be represented as a pregame pick.

The NHL.com lines are editorial and not fixture-attested confirmations. The unresolved Isac Lundestrom identity and incomplete player defensive measurements are explicit blockers. Team shots-against is used for defense; individual defender suppression is not fabricated. Faceoff rate is represented through observed shot/scoring rates, not added as an independent effect. B2B, rest and travel are retained but have no estimated coefficient. Missing these fields blocks a claim that every game situation is represented.

The PR does not replace the published historical outcome-only model or wire this engine to the live daily workflow. That step requires complete, correctly timed pregame inputs and a valid source for the current lineup and unresolved injuries. No post-start input is eligible for publication.

## Validation

Run `python -m unittest nhl.tests.test_joint_match_engine_320 -v`. The tests use the real reconstructed match package to check four goalie combinations, regulation minutes conservation, unresolved-source gating, and sensitivity to skater scoring, shot defense, own PP conversion, opponent PK and penalty exposure. The assist test checks the goal-credit conversion; all sensitivity checks are input perturbations, not evidence of predictive accuracy.
