"""Strict point-in-time NHL feature training rows and coverage audit.

Input is a set of *actually frozen* feature vectors plus separate postgame
labels. No backfilling, post-start source evidence or fake numerical features.
"""
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

FEATURES=("offense_skater_proxy","availability_delta_proxy","pp_bayes","pk_opponent_allowed_bayes","rest_days")
def assemble(snapshots,labels):
 targets={str(r["game_id"]):r for r in labels}
 if len(targets)!=len(labels):raise ValueError("Duplicate labels")
 seen=set();rows=[];rejections=Counter()
 for s in snapshots:
  gid=str(s.get("game_id",""))
  if not gid or gid in seen:raise ValueError("Duplicate/missing frozen snapshot game ID")
  seen.add(gid)
  label=targets.get(gid)
  if label is None:rejections["missing_postgame_label"]+=1;continue
  # Historical label archive must be joined by ID, never used as pregame input.
  try:
   issued=parse_utc(s["as_of"]);start=parse_utc(s["start_utc"])
   if issued>=start:raise ValueError("late")
  except (KeyError,TypeError,ValueError):
   rejections["invalid_or_late_freeze"]+=1;continue
  if s.get("official") is not False or s.get("odds_used") is not False:
   rejections["unverified_model_contract"]+=1;continue
  if s.get("source_attestation_verified") is not True or not s.get("frozen_before_start"):
   rejections["missing_asof_attestation"]+=1;continue
  if not s.get("source_sha256") or len(s["source_sha256"])!=64:
   rejections["missing_digest"]+=1;continue
  if s.get("issues") or s.get("status")!="research_vector_complete":
   rejections["partial_features"]+=1;continue
  if s.get("home")!=label["home"] or s.get("away")!=label["away"] or s.get("date")!=label["date"]:
   rejections["fixture_label_mismatch"]+=1;continue
  teams=s.get("teams",{})
  if set(teams)!={s["home"],s["away"]}:rejections["missing_team_vector"]+=1;continue
  if any(teams[t].get(k) is None for t in (s["home"],s["away"]) for k in FEATURES):
   rejections["missing_numeric_feature"]+=1;continue
  rows.append({"game_id":gid,"date":s["date"],"home":s["home"],"away":s["away"],"frozen_as_of":s["as_of"],
   "source_sha256":s["source_sha256"],"features":{team:{k:teams[team][k] for k in FEATURES} for team in (s["home"],s["away"])},
   "target":{"ml":label["ml_winner"],"rt":label["rt_result"],"first3":label["first_to_plus3"],
    "home3":label["home_reached_plus3"],"away3":label["away_reached_plus3"]}})
 rows.sort(key=lambda r:(r["date"],r["game_id"]))
 return {"status":"training_dataset_research_only","rows":rows,"accepted":len(rows),
   "snapshots_seen":len(snapshots),"reject_reasons":dict(rejections),
   "coverage_of_labeled_games":round(len(rows)/len(labels),6) if labels else 0.,
   "eligible_for_collective_training":len(rows)>=200,
   "note":"Eligibility is sample-size gate only. Historical as-of coverage, heldout validation and full defensive/goalie proof needed.",
   "odds_used":False,"model_promoted":False}
def main():
 p=argparse.ArgumentParser()
 for name in ("snapshots","labels","out"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 snapshots=json.loads(Path(a.snapshots).read_text())
 with Path(a.labels).open(newline="") as f: labels=list(csv.DictReader(f))
 result=assemble(snapshots,labels);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,indent=2));print(json.dumps({k:result[k] for k in ("accepted","snapshots_seen","reject_reasons","coverage_of_labeled_games","eligible_for_collective_training")},indent=2))
if __name__=="__main__":main()
