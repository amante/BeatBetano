# Availability Delta 2.6 — pregame starter and replacement role registry

Implements **validation only**, not a real 2023–25 NFL starter-role dataset and not a fitted injury-impact model.

Required role records: game_id, team, player_id, role, status, snapshot_utc, kickoff_utc, source. Accept only point-in-time authenticated pregame snapshots. Distinguish CB1, CB2, NICKEL, defensive line, QB1 and five offensive-line roles. Do not derive specific roles from generic CB or secondary labels or target-game snap counts.

A replacement record must identify a documented starter absent at kickoff. Candidate replacements are not assigned skill grades, usage or expected snaps without independent pregame evidence. 'Questionable' or 'doubtful' are *not* equivalent to confirmed absent. Missing role information is unknown, not healthy.

**Next**: acquire and license a reliable timestamped NFL depth-chart / inactive / starter-role history, audit its coverage, then build matched multiseason availability deltas and evaluate Brier/log loss before any ML/spread/prop adjustments. Existing verified 2023–24 injury archive cannot establish CB1/CB2/nickel labels on its own.
