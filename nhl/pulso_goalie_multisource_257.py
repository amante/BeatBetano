"""Dated multi-provider NHL goalie evidence, with conservative fixture and name matching.

Daily Faceoff has independently labeled statuses. NHL.com editorial lines remain
projected, never confirmation. Missing a source is NOT a missing starter.
"""
import argparse,json,re,hashlib,unicodedata
from html.parser import HTMLParser
from urllib.request import Request,urlopen
from datetime import datetime,timezone
from pathlib import Path
from nhl.pulso_pregame_v7 import parse_utc

URL="https://www.dailyfaceoff.com/starting-goalies"
TEAM_NAMES={
"ANA":"Anaheim Ducks","BOS":"Boston Bruins","BUF":"Buffalo Sabres","CAR":"Carolina Hurricanes",
"CBJ":"Columbus Blue Jackets","CGY":"Calgary Flames","CHI":"Chicago Blackhawks",
"COL":"Colorado Avalanche","DAL":"Dallas Stars","DET":"Detroit Red Wings",
"EDM":"Edmonton Oilers","FLA":"Florida Panthers","LAK":"Los Angeles Kings",
"MIN":"Minnesota Wild","MTL":"Montreal Canadiens","NJD":"New Jersey Devils",
"NSH":"Nashville Predators","NYI":"New York Islanders","NYR":"New York Rangers",
"OTT":"Ottawa Senators","PHI":"Philadelphia Flyers","PIT":"Pittsburgh Penguins",
"SEA":"Seattle Kraken","SJS":"San Jose Sharks","STL":"St Louis Blues",
"TBL":"Tampa Bay Lightning","TOR":"Toronto Maple Leafs","UTA":"Utah Mammoth",
"VAN":"Vancouver Canucks","VGK":"Vegas Golden Knights","WPG":"Winnipeg Jets",
"WSH":"Washington Capitals"}
def norm(value):
 v=unicodedata.normalize("NFKD",str(value).casefold())
 return re.sub(r"[^a-z0-9]","", "".join(c for c in v if not unicodedata.combining(c)))
class Plain(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ("script","style","noscript"):self.skip+=1
  if tag in ("div","p","h1","h2","h3","li","br"):self.parts.append("\n")
 def handle_endtag(self,tag):
  if tag in ("script","style","noscript") and self.skip:self.skip-=1
  if tag in ("div","p","h1","h2","h3","li"):self.parts.append("\n")
 def handle_data(self,data):
  if not self.skip:self.parts.append(data)
def fetch(url=URL):
 if url!=URL:raise ValueError("Unexpected source")
 with urlopen(Request(url,headers={"User-Agent":"BeatBetano-research/1.0","Accept":"text/html"}),timeout=25) as response:
  raw=response.read(4000000)
  if response.read(1):raise ValueError("Oversized response")
 p=Plain();p.feed(raw.decode("utf-8","replace"))
 return [x.strip() for x in "".join(p.parts).splitlines() if x.strip()],{"source_url":url,"retrieved_at":datetime.now(timezone.utc).isoformat(),"sha256":hashlib.sha256(raw).hexdigest()}
def extract(lines,report,rosters,metadata):
 at=parse_utc(report["generated_at_utc"]);captured=parse_utc(metadata["retrieved_at"])
 if captured<at:raise ValueError("Old provider capture")
 byteam={r["team"]:r for r in rosters["rosters"]}
 matches=[]
 for f in report["games"]:
  start=parse_utc(f["start_utc"])
  if captured>=start:continue
  home=f["home"];away=f["away"]
  headings=[i for i,line in enumerate(lines) if norm(line)==norm(TEAM_NAMES[away]+" at "+TEAM_NAMES[home])]
  if len(headings)!=1:continue
  begin=headings[0];end=min([i for i in range(begin+1,len(lines)) if re.search(r"\sat\s",lines[i]) and any(norm(lines[i])==norm(TEAM_NAMES[a]+" at "+TEAM_NAMES[h]) for a in TEAM_NAMES for h in TEAM_NAMES if a!=h)] or [len(lines)])
  section=lines[begin+1:end]
  # A source-specific timestamp and explicit status must be adjacent to the exact roster goalie name.
  for team in (away,home):
   roster=byteam.get(team)
   if not roster:continue
   candidates=[]
   for p in roster["players"]:
    if p.get("position_group")!="goalie" or not p.get("full_name"):continue
    spots=[i for i,line in enumerate(section) if norm(line)==norm(p["full_name"])]
    for i in spots:
     status=section[i+1] if i+1<len(section) else ""
     if status not in ("Confirmed","Likely","Unconfirmed"):continue
     ts=section[i+2] if i+2<len(section) and re.match(r"20\d\d-\d\d-\d\dT",section[i+2]) else None
     if ts and (parse_utc(ts)>captured or parse_utc(ts)>=start):continue
     candidates.append({"player_id":p["player_id"],"name":p["full_name"],"provider_status":status.lower(),
       "source_reported_at":ts})
   # A full source section may list multiple players on same team: fail closed on ambiguity.
   if len(candidates)==1:
    matches.append({"game_id":str(f["game_id"]),"team":team,**candidates[0],
      "provider":"daily_faceoff","source_url":metadata["source_url"],
      "captured_at":metadata["retrieved_at"],"independent_nhl_confirmation":False})
 return {"kind":"nhl_external_goalie_observations_257","as_of_utc":report["generated_at_utc"],
  "observations":matches,"captured_at":metadata["retrieved_at"],"source_sha256":metadata["sha256"],
  "official_predictions":0,"note":"DFO confirmed is a reported status; not independent NHL team verification."}
def main():
 p=argparse.ArgumentParser()
 for k in ("report","rosters","out"):p.add_argument("--"+k,required=True)
 a=p.parse_args()
 report=json.loads(Path(a.report).read_text());rosters=json.loads(Path(a.rosters).read_text())
 try:
  rows,meta=fetch()
  out=extract(rows,report,rosters,meta)
 except (OSError,TimeoutError,UnicodeError,ValueError) as exc:
  out={"kind":"nhl_external_goalie_observations_257","as_of_utc":report["generated_at_utc"],"observations":[],"source_error":type(exc).__name__,"official_predictions":0,"note":"External provider unavailable; normal pregame lineup process unaffected."}
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(out,indent=2))
 print(json.dumps({"matched_goalie_observations":len(out["observations"]),"official_predictions":0}))
if __name__=="__main__":main()
