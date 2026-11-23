"""Capture RotoWire first for NBA pregame lineups and display-only market context.

Official confirmations retain authority; no paywall bypass or invented data.
"""
import argparse,json,re
from datetime import datetime,timezone
from pathlib import Path
import requests
from team_identity import canonical

from lineup_source_cascade import cascade,markdown
URL="https://www.rotowire.com/basketball/nba-lineups.php"
UA="BeatBetano/1.0 (pregame lineup evidence; contact via repository)"
def parse_market_contexts(html,snapshot,observed):
 """Extract odds from the full RotoWire game card, keeping them display-only.

 RotoWire renders odds/referee rows alongside the nested lineup panel. Search
 the smallest shared ancestor that contains this matchup's lineup and its
 market rows instead of assuming the rows live inside the lineup element.
 """
 try:
  from bs4 import BeautifulSoup
 except ImportError:
  return {}
 soup=BeautifulSoup(html,"html.parser")
 fixtures={frozenset((canonical(g["home_team"]),canonical(g["away_team"]))):g for g in snapshot["predictions"]}
 output={}
 for box in soup.select(".lineup"):
  codes=[x.get_text(" ",strip=True).upper() for x in box.select(".lineup__abbr")]
  codes=[x for x in codes if re.fullmatch("[A-Z]{2,4}",x)]
  if len(codes)!=2 or codes[0]==codes[1]:continue
  game=fixtures.get(frozenset(canonical(x) for x in codes))
  if not game:continue
  market_scope=box
  for parent in box.parents:
   # Reject a page/section wrapper spanning several matchups so rows cannot
   # accidentally be attributed to the wrong game.
   if len(parent.select(".lineup"))>1:continue
   candidate_text=re.sub(r"\s+"," ",parent.get_text(" ",strip=True))
   if re.search(r"\bLINE\s+[A-Z]{2,4}\s+[+-]\d{2,5}\b",candidate_text,re.I) or re.search(r"\bSPREAD\s+[A-Z]{2,4}\s+[+-]\d+(?:\.\d+)?\b",candidate_text,re.I) or re.search(r"\bO/U\s+\d+(?:\.\d+)?\s*Pts\b",candidate_text,re.I):
    market_scope=parent
    break
  text=re.sub(r"\s+"," ",market_scope.get_text(" ",strip=True))
  moneyline=re.search(r"\bLINE\s+([A-Z]{2,4})\s+([+-]\d{2,5})\b",text,re.I)
  spread=re.search(r"\bSPREAD\s+([A-Z]{2,4})\s+([+-]\d+(?:\.\d+)?)\b",text,re.I)
  total=re.search(r"\bO/U\s+(\d+(?:\.\d+)?)\s*Pts\b",text,re.I)
  refs=re.search(r"\bReferees:\s*(.+?)\s+LINE\b",text,re.I)
  referees=[]
  if refs:
   referees=[re.sub(r"\s+"," ",name).strip() for name in re.split(r"\s*,\s*",refs.group(1)) if name.strip()][:3]
  team_by_code={canonical(t):t for t in (game["home_team"],game["away_team"])}
  def team_for(match):
   return team_by_code.get(canonical(match.group(1))) if match else None
  ml_team=team_for(moneyline);spread_team=team_for(spread)
  market={
   "source_provider":"rotowire","source_url":URL,"observed_at_utc":observed,
   "display_only":True,"model_input":False,
   "moneyline":{"team":ml_team,"american_odds":int(moneyline.group(2))} if ml_team else None,
   "spread":{"team":spread_team,"points":float(spread.group(2))} if spread_team else None,
   "total_points":float(total.group(1)) if total else None,"referees":referees}
  if market["moneyline"] or market["spread"] or market["total_points"] is not None or referees:
   output[str(game["game_id"])]=market
 return output

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
    if tag=="li" and self.list_index>=0:self.capture=("player",self.list_index)
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
  fixtures={frozenset((canonical(g["home_team"]),canonical(g["away_team"]))):g for g in snapshot["predictions"]}
  for block in parser.blocks:
   names=[x.upper() for x in block["abbr"] if re.fullmatch("[A-Z]{2,4}",x.upper())]
   if len(names)!=2:continue
   game=fixtures.get(frozenset(canonical(n) for n in names))
   if not game or len(block["lists"])<2:continue
   for team,players in zip(names,block["lists"][:2]):
    team=next(t for t in (game["home_team"],game["away_team"]) if canonical(t)==canonical(team))
    players=players[:5]
    if len(players)!=5 or len(set(players))!=5:continue
    candidates.append({"game_id":str(game["game_id"]),"team":team,"provider":"rotowire","status":"projected","starters":players,"source_url":URL,"observed_at_utc":observed})
  return candidates,errors
 soup=BeautifulSoup(html,"html.parser")
 fixtures={frozenset((canonical(g["home_team"]),canonical(g["away_team"]))):g for g in snapshot["predictions"]}
 candidates=[];errors=[]
 for box in soup.select(".lineup"):
  names=[x.get_text(" ",strip=True).upper() for x in box.select(".lineup__abbr")]
  names=[x for x in names if re.fullmatch("[A-Z]{2,4}",x)]
  if len(names)!=2 or names[0]==names[1]:continue
  game=fixtures.get(frozenset(canonical(n) for n in names))
  if not game:continue
  lists=box.select(".lineup__list")
  if len(lists)<2:
   errors.append({"game_id":game["game_id"],"error":"missing_lineup_lists"});continue
  for team,section in zip(names,lists[:2]):
   team=next(t for t in (game["home_team"],game["away_team"]) if canonical(t)==canonical(team))
   players=[]
   for li in section.select("li"):
    # RotoWire has changed player-row classes over time. The expected-lineup
    # list is already scoped here, so use its linked player names regardless
    # of the decorative row class; injury sections are separate lists.
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
 candidates=[];errors=[];market_contexts={}
 try:
  res=(session or requests.Session()).get(URL,headers={"User-Agent":UA},timeout=12)
  res.raise_for_status()
  candidates,errors=parse_rotowire(res.text,snapshot,observed)
  market_contexts=parse_market_contexts(res.text,snapshot,observed)
 except requests.RequestException as e:
  errors.append({"provider":"rotowire","error":type(e).__name__})
 sources={"candidates":candidates}
 result=cascade(snapshot,sources,observed_at_utc=observed)
 result["market_contexts"]=market_contexts
 result["fetch_url"]=URL;result["fetch_errors"]=errors
 result["fetched_candidates"]=len(candidates)
 result["teams_with_lineups"]=sum(bool(team.get("starters")) for game in result.get("games",{}).values() for team in game.get("teams",{}).values())
 result["lineup_capture_status"]="captured" if result["teams_with_lineups"] else "no_candidates"
 result["lineup_capture_diagnostic"]=None if result["teams_with_lineups"] else "RotoWire loaded, but no five-player lineup matched the current fixture cohort."
 result["notes"]="RotoWire is the primary third-party pregame capture. NBA/team-confirmed lineups retain authority over projections; odds are display-only and may be unavailable."
 return result,sources
def main():
 p=argparse.ArgumentParser()
 for x in ("snapshot","output","summary","candidates"):p.add_argument("--"+x,required=True)
 a=p.parse_args()
 result,sources=collect(json.loads(Path(a.snapshot).read_text()))
 for dest,content in ((a.output,json.dumps(result,indent=2)),(a.summary,markdown(result)),(a.candidates,json.dumps(sources,indent=2))):
  f=Path(dest);f.parent.mkdir(parents=True,exist_ok=True);f.write_text(content)
 print(json.dumps({"fetched_candidates":result["fetched_candidates"],"teams_with_lineups":result["teams_with_lineups"],"lineup_capture_status":result["lineup_capture_status"],"fetched_market_contexts":len(result["market_contexts"]),"errors":len(result["fetch_errors"])}))
if __name__=="__main__":main()
