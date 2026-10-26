"""NBA multifeed evidence: ESPN injury observations + Bleacher Report NBA headlines.

Bleacher Report is an editorial alert source, NEVER official injury/starter
verification. A third party repeating an ESPN report is not independent
confirmation. No odds or market prices enter this collector.
"""
import argparse,json,re,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
import requests

BR_FEED="https://feeds.bleacherreport.com/articles"
INJURY_WORDS=re.compile(r"\b(injur\w*|out|questionable|doubtful|probable|ruled out|return\w*|sidelined|miss\w*|knee|ankle|hamstring|concussion|lineup)\b",re.I)
NBA_WORDS=re.compile(r"\b(nba|basketball|lakers|celtics|warriors|knicks|bulls|heat|cavaliers|mavericks|76ers|sixers|nuggets|suns|bucks|thunder|pacers|pistons|raptors|clippers|spurs|kings|nets|hornets|wizards|timberwolves|rockets|pelicans|jazz|grizzlies|magic|blazers|trail blazers|hawks)\b",re.I)
def utc(value):
 d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
 if d.tzinfo is None:raise ValueError("Timestamp without timezone")
 return d.astimezone(timezone.utc)
def extract_br(xml,observed):
 now=utc(observed)
 result=[]
 root=ET.fromstring(xml)
 for item in root.findall(".//item"):
  title=(item.findtext("title") or "").strip()
  link=(item.findtext("link") or "").strip()
  published=item.findtext("pubDate")
  if urlparse(link).hostname not in ("bleacherreport.com","www.bleacherreport.com") or not published:continue
  try:pub=parsedate_to_datetime(published).astimezone(timezone.utc)
  except (ValueError,TypeError,OverflowError):continue
  if pub>now or not INJURY_WORDS.search(title) or not NBA_WORDS.search(title):continue
  result.append({"headline":title,"url":link,"published_at_utc":pub.isoformat(),
   "collected_at_utc":now.isoformat(),"source":"Bleacher Report","source_type":"editorial_alert",
   "player_identity_verified":False,"official_injury_status_verified":False,
   "confirmed_starting_five":False,"independent_confirmation":False})
 return result
def collect(snapshot,sporting,preview,session=None,observed=None):
 now=utc(observed or datetime.now(timezone.utc).isoformat()).isoformat()
 requester=session or requests.Session()
 stories=[];status="unavailable";error=None
 try:
  response=requester.get(BR_FEED,timeout=25)
  response.raise_for_status()
  stories=extract_br(response.content,now)
  status="retrieved"
 except (requests.RequestException,ET.ParseError,ValueError) as exc:
  error={"error_type":type(exc).__name__,"http_status":getattr(getattr(exc,"response",None),"status_code",None)}
 games={}
 for g in snapshot["predictions"]:
  gid=str(g["game_id"]);tip=utc(g["tipoff_utc"])
  espn=sporting.get("games",{}).get(gid,{}).get("supplementary_injury_observations",{})
  sample=espn.get("items",[]) if isinstance(espn,dict) else []
  observed_at=espn.get("observed_at_utc") if isinstance(espn,dict) else None
  if not observed_at or utc(observed_at)>=tip:sample=[]
  # No unverified automatic BR name/team assignments by headline keywords.
  pregame=[s for s in stories if utc(s["collected_at_utc"])<tip]
  games[gid]={"home_team":g["home_team"],"away_team":g["away_team"],
   "espn_injury_observations":sample,"bleacher_report_headline_alerts":pregame,
   "br_alerts_assigned_to_players":0,"official_status_verified":False,
   "confirmed_starting_fives":False,"independent_sources_confirming_injury":0}
 return {"snapshot_sha256":snapshot["content_sha256"],"collected_at_utc":now,
  "bleacher_report_feed":BR_FEED,"br_retrieval_status":status,"br_error":error,
  "br_nba_injury_headlines":stories,"games":games,
  "final_probabilities_authorized":False,
  "note":"BR editorial headlines may quote ESPN. None are treated as independent confirmed player availability or assigned to a game without roster reconciliation."}
def main():
 ap=argparse.ArgumentParser()
 for flag in ("snapshot","sporting","preview","output"):ap.add_argument("--"+flag,required=True)
 args=ap.parse_args()
 read=lambda name:json.loads(Path(getattr(args,name)).read_text())
 report=collect(read("snapshot"),read("sporting"),read("preview"))
 dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_text(json.dumps(report,indent=2))
 print(json.dumps({"games":len(report["games"]),"br_feed":report["br_retrieval_status"],
   "br_headlines":len(report["br_nba_injury_headlines"]),"official_confirmations":0}))
if __name__=="__main__":main()
