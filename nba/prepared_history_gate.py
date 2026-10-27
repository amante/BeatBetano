"""Reject historical bundles whose target date, cutoff, or files do not match the slate."""
import argparse,json
from datetime import date,datetime,timezone
from pathlib import Path

def verify(target,history,audit,players,teams):
 day=date.fromisoformat(target)
 if audit.get("target_date")!=target:raise ValueError("Historical artifact target date differs")
 t=datetime.fromisoformat(audit["created_at_utc"].replace("Z","+00:00"))
 if t.tzinfo is None or t.utcoffset()!=timezone.utc.utcoffset(t):raise ValueError("Historical timestamp not UTC")
 if not isinstance(history,list) or not history:raise ValueError("Empty history")
 if not isinstance(players,dict) or not isinstance(teams,(dict,list)):raise ValueError("Missing auxiliary datasets")
 for row in history:
  start=datetime.fromisoformat(row["tipoff_utc"].replace("Z","+00:00"))
  if start.tzinfo is None or start.date()>=day or start>=t:
   raise ValueError("Historical event violates pregame chronology")
 if audit.get("source_count")!=len(history):raise ValueError("Historical row count mismatch")
 return {"target_date":target,"historical_games":len(history),"status":"accepted_earlier_completed_history",
   "note":"This validates dates and required files, not full provider integrity or model accuracy."}

def main():
 p=argparse.ArgumentParser()
 for x in ("date","history","audit","players","teams"):p.add_argument("--"+x,required=True)
 a=p.parse_args()
 read=lambda key:json.loads(Path(getattr(a,key)).read_text())
 print(json.dumps(verify(a.date,read("history"),read("audit"),read("players"),read("teams"))))
if __name__=="__main__":main()
