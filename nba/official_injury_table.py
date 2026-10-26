"""Parse explicit NBA injury table rows, including carried-forward team cells.

Supports original official PDF text layout. Parsed rows are observational
records; a source collected after an old snapshot is never backdated.
"""
import re

TEAMS={
"Atlanta Hawks":"ATL","Boston Celtics":"BOS","Brooklyn Nets":"BKN",
"Charlotte Hornets":"CHA","Chicago Bulls":"CHI","Cleveland Cavaliers":"CLE",
"Dallas Mavericks":"DAL","Denver Nuggets":"DEN","Detroit Pistons":"DET",
"Golden State Warriors":"GSW","Houston Rockets":"HOU","Indiana Pacers":"IND",
"Los Angeles Clippers":"LAC","Los Angeles Lakers":"LAL","Memphis Grizzlies":"MEM",
"Miami Heat":"MIA","Milwaukee Bucks":"MIL","Minnesota Timberwolves":"MIN",
"New Orleans Pelicans":"NOP","New York Knicks":"NYK","Oklahoma City Thunder":"OKC",
"Orlando Magic":"ORL","Philadelphia 76ers":"PHI","Phoenix Suns":"PHX",
"Portland Trail Blazers":"POR","Sacramento Kings":"SAC","San Antonio Spurs":"SAS",
"Toronto Raptors":"TOR","Utah Jazz":"UTA","Washington Wizards":"WAS"}
# Do not assume a team cell from a previous page without an explicit game/table context.
TEAM_RE=re.compile("|".join(re.escape(t) for t in sorted(TEAMS,key=len,reverse=True)))
PLAYER_RE=re.compile(r"(?P<last>[A-Za-z][A-Za-z'. -]*(?:, Jr\.|, III|, II|, IV)?)\s*,\s*(?P<first>[A-Za-z][A-Za-z'. -]*?)\s+(?P<status>Questionable|Doubtful|Probable|Available|Out)\b")
MATCHUP_RE=re.compile(r"\b[A-Z]{2,3}@[A-Z]{2,3}\b")
DATE_RE=re.compile(r"\b\d{1,2}/\d{1,2}/20\d{2}\b")
def extract(pages):
 if not isinstance(pages,list):raise ValueError("Expected pages")
 rows=[]
 for page_no,page in enumerate(pages,1):
  team=None;matchup=None;game_date=None
  for line_no,line in enumerate(page.splitlines(),1):
   if "Game Date" in line and "Player Name" in line:continue
   if "Injury Report:" in line or "Page " in line and " of " in line:continue
   dt=DATE_RE.search(line)
   if dt:game_date=dt.group()
   matchup_found=MATCHUP_RE.search(line)
   if matchup_found:matchup=matchup_found.group()
   team_match=TEAM_RE.search(line)
   if team_match:team=TEAMS[team_match.group()]
   if "NOT YET SUBMITTED" in line:
    # No injury rows; store no invented healthy players.
    continue
   # If a new game heading is present without an explicit team, discard context.
   if matchup_found and not team_match:team=None
   candidate=line[team_match.end():] if team_match else line
   hit=PLAYER_RE.search(candidate)
   if not hit or not team:continue
   last=hit.group("last").strip()
   first=hit.group("first").strip()
   if not first or len(last)<2:continue
   rows.append({"team":team,"player":first+" "+last,"status":hit.group("status").title(),
    "game_date":game_date,"matchup":matchup,"page":page_no,"line":line_no,
    "raw":line.strip(),"mapping":"explicit_team_cell_or_same_page_continuation",
    "independently_identity_verified":False})
 return rows
