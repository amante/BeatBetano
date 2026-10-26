"""Report observed source coverage; never upgrade editorial mentions to availability."""
import argparse,json
from pathlib import Path

def score(snapshot, multi, rec, matched):
 expected=snapshot["content_sha256"]
 for label,data in [("multisource",multi),("reconciliation",rec),("roster_matches",matched)]:
  if data.get("snapshot_sha256")!=expected:raise ValueError(label+" snapshot mismatch")
 rows=[];totals={"games":0,"espn_unique_players":0,"espn_duplicate_rows":0,
 "espn_status_conflicts":0,"br_athlete_mentions":0,"br_ambiguous_headlines":0,
 "br_unassigned_editorial_alerts":0,"officially_verified_players":0,"confirmed_starting_fives":0}
 for g in snapshot["predictions"]:
  gid=str(g["game_id"])
  a=rec.get("games",{}).get(gid,{})
  b=matched.get("games",{}).get(gid,{})
  m=multi.get("games",{}).get(gid,{})
  row={"game_id":gid,"home_team":g["home_team"],"away_team":g["away_team"],
   "espn_unique_players":a.get("unique_structured_players",0),
   "espn_duplicate_rows":a.get("duplicate_espn_records",0),
   "espn_status_conflicts":a.get("conflicting_espn_statuses",0),
   "br_athlete_mentions":b.get("matched_count",0),
   "br_ambiguous_headlines":b.get("ambiguous_headlines",0),
   "br_unassigned_editorial_alerts":max(0,len(m.get("bleacher_report_headline_alerts",[]))-b.get("matched_count",0)),
   "officially_verified_players":0,"confirmed_starting_fives":0,
   "evidence_only":True}
  rows.append(row)
  totals["games"]+=1
  for k in totals:
   if k!="games":totals[k]+=row[k]
 errors=matched.get("roster_retrieval_errors",{})
 return {"snapshot_sha256":expected,"summary":totals,"by_game":rows,
  "br_retrieval_status":multi.get("br_retrieval_status","unknown"),
  "br_reported_headlines_total":len(multi.get("br_nba_injury_headlines",[])),
  "roster_source":"ESPN","roster_errors":errors,"teams_with_roster_errors":len(errors),
  "source_coverage_verification":"not_verified",
  "calibrated_probabilities_authorized":False,
  "note":"Matched BR editorial mentions are not unique injury events, independent confirmations or official player statuses."}
def markdown(r):
 s=r["summary"]
 lines=["## NBA independent evidence coverage (not official verification)","",
  "| Metric | Observed |","|---|---:|"]
 for k,v in s.items():lines.append("| "+k.replace("_"," ")+" | "+str(v)+" |")
 lines+=["| BR feed status | "+str(r["br_retrieval_status"])+" |",
         "| ESPN roster errors (teams) | "+str(r["teams_with_roster_errors"])+" |",
         "","**No official player availability or confirmed starting fives can be inferred from these feeds.**"]
 return "\n".join(lines)+"\n"
def main():
 p=argparse.ArgumentParser()
 for key in ("snapshot","multisource","reconciliation","matched","output","summary"):p.add_argument("--"+key,required=True)
 a=p.parse_args()
 read=lambda k:json.loads(Path(getattr(a,k)).read_text())
 r=score(read("snapshot"),read("multisource"),read("reconciliation"),read("matched"))
 for key,data in (("output",json.dumps(r,indent=2)),("summary",markdown(r))):
  f=Path(getattr(a,key));f.parent.mkdir(parents=True,exist_ok=True);f.write_text(data)
 print(json.dumps(r["summary"]))
if __name__=="__main__":main()
