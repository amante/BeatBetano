"""Merge verified NHL game artifacts and select next missing games.

Local JSON files may contain any subset of the historical ledger.
Only complete, matching records count as covered.
"""
import argparse,json,shutil
from pathlib import Path

def consolidate(ledger,source_dirs,destination):
    destination.mkdir(parents=True,exist_ok=True)
    known={str(r["id"]):r for r in ledger}
    seen={};conflicts=[];invalid=[]
    for directory in source_dirs:
        for path in sorted(Path(directory).rglob("*.json")):
            if path.name=="manifest.json":continue
            try:obj=json.loads(path.read_text())
            except (OSError,ValueError):invalid.append(str(path));continue
            gid=str(obj.get("game_id",""))
            expected=known.get(gid)
            if (not expected or obj.get("date")!=expected["date"]
                or obj.get("home")!=expected["home"] or obj.get("away")!=expected["away"]
                or not obj.get("goal_events_available")
                or not obj.get("boxscore",{}).get("player_by_game_stats")):
                invalid.append(str(path));continue
            compact=json.dumps(obj,sort_keys=True,separators=(",",":"))
            if gid in seen and seen[gid]!=compact:
                conflicts.append(gid)
            else:seen[gid]=compact
    if conflicts:raise ValueError("Conflicting game records: "+str(conflicts[:10]))
    for gid,content in seen.items(): (destination/(gid+".json")).write_text(content)
    ids={str(row["id"]) for row in ledger}
    missing=[row for row in ledger if str(row["id"]) not in seen]
    stats={"ledger_games":len(ids),"consolidated_games":len(seen),
       "missing_games":len(missing),"invalid_files":invalid,
       "source_folders":[str(p) for p in source_dirs],
       "next_missing_id":missing[0]["id"] if missing else None,
       "status":"postgame_archive_not_pregame_validated"}
    (destination/"manifest.json").write_text(json.dumps(stats,indent=2))
    return stats,missing

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",required=True)
    p.add_argument("--source-dir",action="append",required=True)
    p.add_argument("--output-dir",required=True)
    p.add_argument("--selection-file",required=True)
    p.add_argument("--batch-size",type=int,default=100)
    args=p.parse_args()
    if not 1<=args.batch_size<=150:raise ValueError("Invalid batch size")
    ledger=json.loads(Path(args.ledger).read_text())
    stats,missing=consolidate(ledger,args.source_dir,Path(args.output_dir))
    selected=missing[:args.batch_size]
    dest=Path(args.selection_file);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(selected))
    print(json.dumps({**stats,"next_batch":len(selected)}))
if __name__=="__main__":main()
