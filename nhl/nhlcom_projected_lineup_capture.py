"""Capture NHL.com projected-lineup report safely as *source observations*.

The HTML is saved unmodified with capture time/hash. Only unambiguous textual
sections are extracted. Player IDs and confirmed starters are deliberately NOT
fabricated from free text. Never feed raw names to numeric CRS by accident.
"""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request,urlopen

URL="https://www.nhl.com/news/nhl-lineup-projections-2026-27-season"
class Text(HTMLParser):
 def __init__(self):
  super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ("script","style","noscript"):self.skip+=1
  if tag in ("p","h1","h2","h3","h4","li","div","br"):self.parts.append("\n")
 def handle_endtag(self,tag):
  if tag in ("script","style","noscript") and self.skip:self.skip-=1
  if tag in ("p","h1","h2","h3","h4","li","div"):self.parts.append("\n")
 def handle_data(self,data):
  if not self.skip:self.parts.append(data)

HEADING=re.compile(r"^(.+?) (projected lineup)$",re.I)
MARKERS=("Scratched:","Injured:","Status report")
def extract(html):
 parser=Text();parser.feed(html)
 lines=[re.sub(r"\s+"," ",s).strip() for s in "".join(parser.parts).splitlines()]
 lines=[s for s in lines if s]
 blocks=[];current=None;section="lineup"
 for line in lines:
  m=HEADING.match(line)
  if m:
   if current:blocks.append(current)
   current={"reported_team_name":m.group(1),"lineup_type":"projected","lines":[],"scratched":[],"injured":[]}
   section="lineup";continue
  if current is None:continue
  if line=="Status report":
   blocks.append(current);current=None;continue
  if line.startswith("Scratched:"):
   current["scratched"]=[x.strip() for x in line.split(":",1)[1].split(",") if x.strip()];section="scratched";continue
  if line.startswith("Injured:"):
   raw=line.split(":",1)[1].strip()
   current["injured"]=[] if raw.lower()=="none" else [x.strip() for x in raw.split(",") if x.strip()]
   section="injured";continue
  if section=="lineup" and len(current["lines"])<30 and line not in ("None","Projected lineups, starting goalies for today"):
   current["lines"].append(line)
 if current:blocks.append(current)
 # duplicates or missing line lists are a hard error, not an assumed lineup.
 if not blocks or len({x["reported_team_name"] for x in blocks})!=len(blocks):
  raise ValueError("Unrecognized or ambiguous NHL.com lineup article structure")
 return blocks

def capture(url=URL,timeout=25):
 if url!=URL:raise ValueError("Unapproved source URL")
 with urlopen(Request(url,headers={"User-Agent":"BeatBetano-research/1.0","Accept":"text/html"}),timeout=timeout) as response:
  raw=response.read(4_000_000)
  if response.read(1):raise ValueError("Oversized article")
 captured=datetime.now(timezone.utc).isoformat()
 result={"source_url":url,"retrieved_at":captured,"raw_sha256":hashlib.sha256(raw).hexdigest(),
  "source_class":"NHL.com editorial projected lineup report",
  "blocks":extract(raw.decode("utf-8","replace")),
  "publication_date_verified":False,"fixture_mapping_verified":False,
  "player_ids_resolved":False,"starters_confirmed":False,
  "prediction_eligible":False,
  "note":"Report may refer to earlier calendar day. Before any game use, verify publication date, matchup schedule, name-to-player-ID, and before-game timestamp."}
 return raw,result

def main():
 p=argparse.ArgumentParser();p.add_argument("--output",required=True);p.add_argument("--raw-output",required=True)
 a=p.parse_args();raw,result=capture()
 out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,indent=2));Path(a.raw_output).write_bytes(raw)
 print(json.dumps({"blocks":len(result["blocks"]),"retrieved_at":result["retrieved_at"],
  "player_ids_resolved":False,"prediction_eligible":False},indent=2))
if __name__=="__main__":main()
