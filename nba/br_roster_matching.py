"""Match BR headlines to independently fetched ESPN roster identities, never inferred availability."""
import argparse,json,re
from pathlib import Path
from datetime import datetime,timezone
import requests

ROSTER="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team}/roster"
def stamp(x):
 d=datetime.fromisoformat(str(x).replace("Z","+00:00"))
 if d.tzinfo is None:raise ValueError("timezone required")
 return d.astimezone(timezone.utc)
def roster_names(payload):
 athletes=payload.get("athletes",[])
 if not isinstance(athletes,list):return []
 names=[]
 for group in athletes:
  if not isinstance(group,dict):continue
  members=group.get("items") if isinstance(group.get("items"),list) else [group]
  for athlete in members:
   if isinstance(athlete,dict) and athlete.get("displayName"):
    names.append({"name":athlete["displayName"],"id":str(athlete.get("id") or "")})
 return names
def contains(headline,name):
 # Exact, bounded, case-insensitive full-name match avoids common surname collisions.
 return bool(re.search(r"(?<![\w])"+re.escape(name)+r"(?![\w])",headline,re.I))
def match(snapshot,evidence,session=None):
 if snapshot.get("content_sha256")!=evidence.get("snapshot_sha256"):raise ValueError("Snapshot mismatch")
 requester=session or requests.Session()
 teams=sorted({g[k] for g in snapshot["predictions"] for k in ("home_team","away_team")})
 rosters={};errors={}
 for team in teams:
  try:
   r=requester.get(ROSTER.format(team=team.lower()),timeout=25);r.raise_for_status()
   rosters[team]=roster_names(r.json())
   if not rosters[team]:errors[team]="empty_roster"
  except (requests.RequestException,ValueError,TypeError,KeyError) as exc:
   rosters[team]=[];errors[team]=type(exc).__name__
 games={}
 for game in snapshot["predictions"]:
  gid=str(game["game_id"]);tip=stamp(game["tipoff_utc"])
  alerts=evidence.get("games",{}).get(gid,{}).get("bleacher_report_headline_alerts",[])
  rows=[];ambiguous=0
  for alert in alerts:
   if not isinstance(alert,dict):continue
   try:
    if stamp(alert["published_at_utc"])>stamp(alert["collected_at_utc"]) or stamp(alert["collected_at_utc"])>=tip:continue
   except (ValueError,KeyError,TypeError):continue
   headline=str(alert.get("headline") or "")
   found=[{"team":team,"player":p["name"],"espn_athlete_id":p["id"]}
    for team in (game["home_team"],game["away_team"])
    for p in rosters.get(team,[]) if contains(headline,p["name"])]
   # Require exactly one matching athlete from the teams in this fixture.
   if len(found)!=1:
    ambiguous+=int(len(found)>1)
    continue
   rows.append({**found[0],"headline":headline,"url":alert.get("url"),
     "published_at_utc":alert["published_at_utc"],"collected_at_utc":alert["collected_at_utc"],
     "source":"Bleacher Report","evidence_type":"editorial_headline_only",
     "availability_status":None,"injury_confirmed":False,"starter_confirmed":False,
     "independent_confirmation":False})
  games[gid]={"matched_editorial_mentions":rows,"matched_count":len(rows),
   "ambiguous_headlines":ambiguous,"official_status_verified":False,
   "final_probabilities_authorized":False}
 return {"snapshot_sha256":snapshot["content_sha256"],"roster_source":"ESPN",
  "roster_retrieval_errors":errors,"games":games,
  "note":"Roster-based identity match is not an injury diagnosis, reported availability, independent verification or lineup confirmation."}
def main():
 p=argparse.ArgumentParser()
 for arg in ("snapshot","multisource","output"):p.add_argument("--"+arg,required=True)
 a=p.parse_args();load=lambda f:json.loads(Path(f).read_text())
 r=match(load(a.snapshot),load(a.multisource))
 dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(r,indent=2))
 print(json.dumps({"games":len(r["games"]),"matched_editorial_mentions":sum(x["matched_count"] for x in r["games"].values()),"roster_errors":r["roster_retrieval_errors"]}))
if __name__=="__main__":main()
