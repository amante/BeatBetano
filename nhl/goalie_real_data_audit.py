"""Audit observational goalie evidence from live pregame crosswalk and frozen history.

Coverage and comparison are descriptive, not prospective validation of a
prediction model. An invalid match cannot silently enter the rated subset.
"""
import argparse,json,hashlib
from collections import Counter
from pathlib import Path
try:
 from nhl.goalie_daily_evidence import assess
except ModuleNotFoundError:
 from goalie_daily_evidence import assess

def audit(crosswalk,history,rosters):
 scored=assess(crosswalk,history,rosters)
 counts=Counter()
 for row in scored["goalies"]:
  counts["observations"]+=1
  if row["goalie_player_id"] is not None:counts["identity_eligible"]+=1
  if row["historical_goalie_rating"] is not None:counts["historically_rated"]+=1
  if any(x["rating"] for x in row["alternative_goalies"]):counts["backup_with_history"]+=1
  if any(x["delta_shrunk_save_pct"] is not None for x in row["comparison"]):counts["numeric_backup_comparison"]+=1
  if row["historical_goalie_rating"] is None:counts["not_rated"]+=1
 return {"summary":dict(counts),"goalies":scored["goalies"],
   "historical_metric":"prior-date team goalie SV%, shrunk with 100-shot prior at .905",
   "validation_class":"descriptive real-source coverage audit, NOT chronological backtest",
   "calibrated_win_probability":False,"official_model_promoted":False,"odds_used":False}

def main():
 p=argparse.ArgumentParser()
 for key in ("crosswalk","history","rosters","output"):p.add_argument("--"+key,required=True)
 a=p.parse_args()
 raw={x:Path(getattr(a,x)).read_bytes() for x in ("crosswalk","history","rosters")}
 result=audit(*(json.loads(raw[k]) for k in ("crosswalk","history","rosters")))
 result["input_sha256"]={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
 path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(result,indent=2));print(json.dumps(result["summary"],indent=2))
if __name__=="__main__":main()
