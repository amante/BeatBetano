"""Sequential bounded historical acquisition; one persistent cache and final dataset.

One Actions run contains a succession of batches. Failures remain explicit;
never treat skipped or unverified games as successfully captured.
"""
import argparse,csv,hashlib,json,time
from pathlib import Path
from nhl.pulso_historical_boxscores_265 import capture
from nhl.pulso_historical_features_267 import produce

def execute(labels,cache_dir,start=0,stop=None,batch_size=100,delay=1.0,fetcher=None,sleeper=time.sleep):
    total=len(labels)
    if stop is None:stop=total
    if not (0<=start<stop<=total and 1<=batch_size<=300 and 0<=delay<=10):
        raise ValueError("Invalid sequential batch bounds")
    if len({str(r["game_id"]) for r in labels})!=total:
        raise ValueError("Duplicate historical fixtures")
    cache=Path(cache_dir);cache.mkdir(parents=True,exist_ok=True)
    batches=[]
    from nhl.pulso_historical_boxscores_265 import fetch as official_fetch
    for offset in range(start,stop,batch_size):
        segment=labels[offset:min(offset+batch_size,stop)]
        info=capture(segment,cache,fetcher=fetcher or official_fetch)
        batches.append({"start":offset,"end_exclusive":offset+len(segment),
                        "attempted":info["attempted"],
                        "with_explicit_starters":info["with_explicit_starters"],
                        "status_counts":{k:sum(r["status"]==k for r in info["records"]) for k in sorted({r["status"] for r in info["records"]})}})
        if offset+len(segment)<stop and delay:sleeper(delay)
    records=[]
    for row in labels:
        path=cache/(str(row["game_id"])+".json")
        if path.exists():
            record=json.loads(path.read_text())
            if any(record.get(k)!=row[k] for k in ("date","home","away")):
                raise ValueError("Cached fixture identity mismatch")
            if "verified_starters" not in record:raise ValueError("Incomplete cached evidence")
            records.append(record)
    report=produce(labels,records)
    report["batch_report"]={"start":start,"stop":stop,"batch_size":batch_size,
                             "completed_batches":batches,
                             "captured_games":len(records),"all_historical_labels":total,
                             "source_coverage_fraction":len(records)/total,
                             "complete_source_coverage":len(records)==total}
    return report

def main():
    p=argparse.ArgumentParser()
    for name in ("labels","manifest","cache-dir","out"):p.add_argument("--"+name,required=True)
    p.add_argument("--start",type=int,default=0)
    p.add_argument("--stop",type=int,default=2811)
    p.add_argument("--batch-size",type=int,default=100)
    p.add_argument("--delay",type=float,default=1.0)
    args=p.parse_args()
    path=Path(args.labels)
    meta=json.loads(Path(args.manifest).read_text())
    if meta.get("games")!=2811 or meta.get("sha256")!=hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError("Invalid historical source digest")
    with path.open(newline="") as stream:labels=list(csv.DictReader(stream))
    if len(labels)!=2811:raise ValueError("Unexpected historical labels")
    report=execute(labels,args.cache_dir,args.start,args.stop,args.batch_size,args.delay)
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2))
    print(json.dumps({"batches":len(report["batch_report"]["completed_batches"]),
                      "captured_games":report["batch_report"]["captured_games"],
                      "eligible_count":report["eligible_count"],"blocked_count":report["blocked_count"],
                      "complete_source_coverage":report["batch_report"]["complete_source_coverage"]}))
if __name__=="__main__":main()
