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
# The official PDF layout extractor inserts variable-width spaces between
# words in table cells (for example ``Boston  Celtics`` and ``Milwaukee    Bucks``).
# Match those cells without weakening the player/team association rule. The
# report itself also labels the Clippers as ``LA Clippers``.
TEAMS["LA Clippers"]="LAC"
def _team_pattern(name):
 return r"\s+".join(re.escape(part) for part in name.split())
TEAM_RE=re.compile("|".join(_team_pattern(t) for t in sorted(TEAMS,key=len,reverse=True)),re.I)
TEAM_CODES={" ".join(name.casefold().split()):code for name,code in TEAMS.items()}
PLAYER_RE=re.compile(r"(?P<last>[^\W\d_][\w.'’ -]*(?:,\s*(?:Jr\.|III|II|IV))?)\s*,\s*(?P<first>[^\W\d_][\w.'’ -]*?)\s+(?P<status>Questionable|Doubtful|Probable|Available|Out)\b",re.UNICODE)
MATCHUP_RE=re.compile(r"\b[A-Z]{2,3}@[A-Z]{2,3}\b")
DATE_RE=re.compile(r"\b\d{1,2}/\d{1,2}/20\d{2}\b")
def extract(pages, continuous_table=False):
 if not isinstance(pages,list):raise ValueError("Expected pages")
 if continuous_table:
  # Layout mode pads and indents cells. Canonicalize whitespace before
  # confirming the repeated report header, otherwise valid multi-page tables
  # silently fall back to page-local parsing and lose carried-forward context.
  headers=[next((" ".join(line.split()) for line in page.splitlines()
                 if " ".join(line.split()).startswith('Injury Report:')),None)
           for page in pages]
  normalized_first=[" ".join(line.split()) for line in pages[0].splitlines()]
  if (not headers or not all(headers) or len(set(headers))!=1
          or not any('Game Date' in line and 'Player Name' in line for line in normalized_first)):
   raise ValueError('Continuous table requires identical report headers and an initial table heading')
 rows=[]
 matchup=None;game_date=None;previous_team=None
 for page_no,page in enumerate(pages,1):
  # A team cell can be vertically centered across many player rows and may
  # fall after a page break. Carry context only when this page has no new game
  # marker; otherwise leave leading rows unresolved for the unique roster
  # crosswalk instead of assigning them to the preceding team.
  lines=page.splitlines()
  if not continuous_table:
   team=None;matchup=None;game_date=None
  elif page_no==1 or any(MATCHUP_RE.search(line) for line in lines):
   # A new matchup on this page means leading unlabeled rows could belong to
   # its vertically merged team cell; defer those rows to the roster crosswalk.
   team=None
  else:
   # With matching report headers and no new game marker, this page continues
   # the previous game/team block (the common page-break case).
   team=previous_team
  date_positions=[(i,DATE_RE.search(line)) for i,line in enumerate(lines) if DATE_RE.search(line)]
  first_page_date=date_positions[0][1].group() if date_positions else None
  for line_no,line in enumerate(lines,1):
   if "Game Date" in line and "Player Name" in line:continue
   if "Injury Report:" in line or "Page " in line and " of " in line:continue
   dt=DATE_RE.search(line)
   if dt:game_date=dt.group()
   elif game_date is None and first_page_date:
    # In NBA's table the date cell is merged vertically and pypdf places its
    # text at the cell's center. Apply that first date to rows above its label.
    game_date=first_page_date
   matchup_found=MATCHUP_RE.search(line)
   if matchup_found:matchup=matchup_found.group()
   team_match=TEAM_RE.search(line)
   if team_match:
    team=TEAM_CODES[" ".join(team_match.group().casefold().split())]
   if "NOT YET SUBMITTED" in line:
    # No injury rows; store no invented healthy players.
    continue
   # If a new game heading is present without an explicit team, discard context.
   if matchup_found and not team_match:team=None
   candidate=line[team_match.end():] if team_match else line
   hit=PLAYER_RE.search(candidate)
   if not hit or (not team and not continuous_table):continue
   last=hit.group("last").strip()
   first=hit.group("first").strip()
   if not first or len(last)<2:continue
   rows.append({"team":team,"player":first+" "+last,"status":hit.group("status").title(),
    "game_date":game_date,"matchup":matchup,"page":page_no,"line":line_no,
    "raw":line.strip(),"mapping":"explicit_team_cell_or_same_page_continuation" if team else "team_label_deferred_to_unique_fixture_roster_match",
    "independently_identity_verified":False})
  previous_team=team
 return rows

def extract_team_submissions(pages):
 """Extract only explicit team-level NOT YET SUBMITTED markers."""
 if not isinstance(pages,list):raise ValueError("Expected pages")
 rows=[]
 for page_no,page in enumerate(pages,1):
  game_date=None;matchup=None
  for line_no,line in enumerate(page.splitlines(),1):
   if "Game Date" in line and "Player Name" in line:continue
   if "Injury Report:" in line or "Page " in line and " of " in line:continue
   dt=DATE_RE.search(line)
   if dt:game_date=dt.group()
   matchup_found=MATCHUP_RE.search(line)
   if matchup_found:matchup=matchup_found.group()
   if "NOT YET SUBMITTED" not in line:continue
   team_match=TEAM_RE.search(line)
   if not team_match:continue
   rows.append({"team":TEAMS[team_match.group()],"game_date":game_date,
    "matchup":matchup,"status":"not_yet_submitted","page":page_no,
    "line":line_no,"raw":line.strip()})
 unique={(r["team"],r["game_date"],r["matchup"]):r for r in rows}
 return list(unique.values())
