# NBA player prop signal — informational only

This feature screens **individual** player props for the user to inspect. It
does not create parlays, recommend a wager, train a model, or change any game
probability.

## GOLDEN TICKET eligibility

A signal is emitted only when every required item has a point-in-time source:

1. The player is verified as the highest-usage player on their team, with
   complete team usage coverage.
2. The player's position is verified and the opponent is among the five worst
   defenses against that position (normalized ranks 26–30, where 30 is worst).
3. A pregame RotoWire line and direction exist for Points, Rebounds, Assists,
   or PRA.
4. On the same line and direction, the player's complete current-season sample
   has at least 10 non-push games and at least a 90% hit rate.
5. The player's complete history against this opponent has at least 5
   non-push games and at least a 90% hit rate.

When this report is connected to PULSO, the qualifying prop should appear with
a ticket icon. Its accessible label should explain that it is an informational
prop to evaluate. It must not combine signals into a parlay.

## Evidence contract and current coverage

`player_prop_signal.py` accepts normalized, timestamped source observations.
Each game's `props` rows carry the exact prop line, usage evidence, verified
position and opponent defense rank, plus player boxscore history with game IDs
and tipoff times. The evaluator recomputes hit rates from the rows; it does not
trust provider-supplied percentages. Pushes are excluded from the denominator.
All source observations must predate the fixture tipoff.

Current NBA publication already has player boxscore observations and PTS/REB/AST
projections. It does **not** yet guarantee complete current-season history,
verified team usage rankings, defense-vs-position bottom-five ranks, or a captured
RotoWire player-prop line feed. Therefore the engine must not emit a ticket
from today's publication until those source adapters provide this evidence.
Missing or incomplete evidence is a block, never a zero or an estimated value.

## Integration boundary

The report contract sets `model_probability_input=false` and
`parlay_generation=false`. It is separate from the Elo, Challenger, Hybrid,
injury, travel, lineup, and player-projection calculations. The next connection
step is to archive the source inputs prospectively, attach the report to each
fixture, and render it inside the game's expandable details.
