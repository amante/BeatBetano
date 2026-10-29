# PULSO NHL PR #215 — actual historical as-of training cohort

This dataset builder accepts only **previously frozen pregame feature vectors** with matching official postgame fixture labels. It enforces unique game identity, matching teams and date, freeze timestamp strictly before puck drop, source digest and explicit independent source attestation. Required numerical feature fields are never fabricated or imputed. The postgame labels are used solely as targets after verification.

Inputs: JSON list of externally frozen, provenance-attested snapshots and the verified NHL historical postgame CSV. Output includes retained research rows, rejected-snapshot reasons and coverage. CLI: python -m nhl.pulso_training_ledger_215 --snapshots ledger.json --labels nhl_postgame_labels.csv --out training.json.

Important integration boundary: #214 provides a **research feature vector**, not complete source attestation, game start, date, home/away or guaranteed permanent storage. A separate point-in-time collector must populate and independently verify those fields. The current 2,811-game archive contains labels but NOT historical source-frozen player, goalie, CRS and PP/PK vectors. Until sufficient real eligible rows exist, do **not** train an enhanced model from that archive. The 200-game threshold is only a minimum sample-size flag, not proof of predictive validation.

No market odds; no official probability emission or production promotion. Next work: feed actual auditable prospective frozen records and evaluate date-split model only when enough verified games have matured.
