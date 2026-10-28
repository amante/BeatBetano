"""Merge daily scoreboard observations into durable historical event ledger."""
import argparse,json
from pathlib import Path

def merge(old,fresh):
 if not isinstance(old,list) or not isinstance(fresh,list):raise ValueError("Expected lists")
 rows={}
 for game in old+fresh:
  if not isinstance(game,dict) or not game.get("id") or not game.get("sport"):raise ValueError("Invalid event")
  key=str(game["sport"])+":"+str(game["id"])
  previous=rows.get(key)
  if previous and previous.get("completed") and not game.get("completed"):continue
  rows[key]=game
 return sorted(rows.values(),key=lambda g:(g["start_utc"],g["sport"],str(g["id"])))

def main():
 p=argparse.ArgumentParser();p.add_argument("--daily",required=True);p.add_argument("--history",required=True)
 a=p.parse_args();path=Path(a.history)
 historical=json.loads(path.read_text()) if path.exists() else []
 daily=json.loads(Path(a.daily).read_text())
 merged=merge(historical,daily["games"])
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(merged,ensure_ascii=False,separators=(",",":")))
 print("Retained unique fixtures:",len(merged))
if __name__=="__main__":main()
