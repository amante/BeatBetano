"""Collect attributed pretip projected/confirmed NBA quintets from RotoWire HTML.

No odds extraction, no paywall bypass, and no invented data if page layout changes.
"""
import argparse,json,re
from datetime import datetime,timezone
from pathlib import Path
import requests

from lineup_source_cascade import cascade,markdown
URL="https://www.rotowire.com/basketball/nba-lineups.php"
UA="BeatBetano/1.0 (pregame lineup evidence; contact via repository)"
def parse_rotowire(html,snapshot,observed):
 try:
  from bs4 import BeautifulSoup
 except ImportError:
  # Some repository CI jobs intentionally run without optional scraping packages.
  # Use the standard-library fallback to keep tests and extraction functional.
  from html.parser import HTMLParser
  class Parser(HTMLParser):
   def __init__(self):
    super().__init__();self.blocks=[];self.current=None;self.list_index=-1;self.capture=None
   def handle_starttag(self,tag,attrs):
    props=dict(attrs);classes=props.get("class","").split()
    if "lineup" in classes and self.current is None:
     self.current={"abbr":[],"lists":[]};self.blocks.append(self.current)
    if self.current is None:return
    if "lineup__abbr" in classes:self.capture=("abbr",None)
    if "lineup__list" in classes:
     self.current["lists"].append([]);self.list_index=len(self.current["lists"])-1
    if "lineup__player" in classes and self.list_index>=0:self.capture=("player",self.list_index)
   def handle_data(self,data):
    if self.current is None or self.capture is None:return
    kind,index=self.capture;v=data.strip()
    if not v:return
    if kind=="abbr":self.current["abbr"].append(v)
    elif kind=="player":self.current["lists"][index].append(v)
   def handle_endtag(self,tag):
    if tag=="li" and self.capture and self.capture[0]=="player":self.capture=None
    if tag in ("div","span") and self.capture and self.capture[0]=="abbr":self.capture=None
    if tag=="ul":self.list_index=-1
  parser=Parser();parser.feed(html)
  candidates=[];errors=[]
  fixtures={frozenset((g["home_team"],g["away_team"])):g for g in snapshot["predictions"]}
  for block in parser.blocks:
   names=[x.upper() for x in block["abbr"] if re.fullmatch("[A-Z]{2,4}",x.upper())]
   if len(names)!=2:continue
   game=fixtures.get(frozenset(names))
   if not game or len(block["lists"])<2:continue
   for team,players in zip(names,block["lists"][:2]):
    players=players[:5]
    if len(players)!=5 or len(set(players))!=5:continue
    candidates.append({"game_id":str(game["game_id"]),"team":team,"provider":"rotowire","status":"projected","starters":players,"source_url":URL,"observed_at_utc":observed})
  return candidates,errors
 soup=BeautifulSoup(html,"html.parser")
 fixtures={frozenset((g["home_team"],g["away_team"])):g for g in snapshot["predictions"]}
 candidates=[];errors=[]
 for box in soup.select(".lineup"):
  names=[x.get_text(" ",strip=True).upper() for x in box.select(".lineup__abbr")]
  names=[x for x in names if re.fullmatch("[A-Z]{2,4}",x)]
  if len(names)!=2 or names[0]==names[1]:continue
  game=fixtures.get(frozenset(names))
  if not game:continue
  lists=box.select(".lineup__list")
  if len(lists)<2:
   errors.append({"game_id":game["game_id"],"error":"missing_lineup_lists"});continue
  for team,section in zip(names,lists[:2]):
   players=[]
   for li in section.select("li"):
    # Do not read benched/injured player sections.
    cl=" ".join(li.get("class",[]))
    if "lineup__player" not in cl:continue
    p=li.select_one("a") or li.select_one(".lineup__player-name")
    label=p.get_text(" ",strip=True) if p else ""
    if label:players.append(label)
   players=players[:5]
   if len(players)!=5 or len(set(players))!=5:
    errors.append({"game_id":game["game_id"],"team":team,"error":"five_starters_not_extractable"});continue
   title=section.select_one(".lineup__title")
   if not title:
    title=box.select_one(".lineup__title")
   heading=title.get_text(" ",strip=True).lower() if title else ""
   status="confirmed" if "confirmed lineup" in heading else "projected"
   candidates.append({"game_id":str(game["game_id"]),"team":team,"provider":"rotowire","status":status,
    "starters":players,"source_url":URL,"observed_at_utc":observed})
 return candidates,errors
def collect(snapshot,session=None,observed=None):
 observed=observed or datetime.now(timezone.utc).isoformat()
 candidates=[];errors=[]
 try:
  res=(session or requests.Session()).get(URL,headers={"User-Agent":UA},timeout=12)
  res.raise_for_status()
  candidates,errors=parse_rotowire(res.text,snapshot,observed)
 except requests.RequestException as e:
  errors.append({"provider":"rotowire","error":type(e).__name__})
 sources={"candidates":candidates}
 result=cascade(snapshot,sources,observed_at_utc=observed)
 result["fetch_url"]=URL;result["fetch_errors"]=errors
 result["fetched_candidates"]=len(candidates)
 result["notes"]="RotoWire is third-party evidence, not league-confirmed; selectors are validated fail-closed, may yield no data."
 return result,sources
def main():
 p=argparse.ArgumentParser()
 for x in ("snapshot","output","summary","candidates"):p.add_argument("--"+x,required=True)
 a=p.parse_args()
 result,sources=collect(json.loads(Path(a.snapshot).read_text()))
 for dest,content in ((a.output,json.dumps(result,indent=2)),(a.summary,markdown(result)),(a.candidates,json.dumps(sources,indent=2))):
  f=Path(dest);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(content)
 print(json.dumps({"fetched_candidates":result["fetched_candidates"],"errors":len(result["fetch_errors"])}))
if __name__=="__main__":main()
