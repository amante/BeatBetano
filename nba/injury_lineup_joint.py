"""Joint NBA injury / starting-five evidence.

Never equates ESPN boxscore starters with pre-tipoff confirmed starters.
Parses official NBA PDF text conservatively; ambiguous rows remain unverified.
"""
import argparse,json,re
from pathlib import Path
from datetime import datetime,timezone

STATUS=re.compile(r"\b(Out|Doubtful|Questionable|Probable|Available)\b",re.I)
TEAM_CODES={"ATL","BOS","BKN","CHA","CHI","CLE","DAL","DEN","DET","GSW","HOU","IND","LAC","LAL","MEM","MIA","MIL","MIN","NOP","NYK","OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS"}
ALIASES={"GS":"GSW","NO":"NOP","SA":"SAS","NY":"NYK","UTAH":"UTA"}

def normalize_team(code):
    key=str(code).strip().upper()
    key=ALIASES.get(key,key)
    return key if key in TEAM_CODES else None

def parse_lines(raw_pages):
    if not isinstance(raw_pages,list):raise ValueError("Expected PDF page text list")
    rows=[]
    for page_no,page in enumerate(raw_pages,1):
        if not isinstance(page,str):continue
        for line_no,line in enumerate(page.splitlines(),1):
            m=STATUS.search(line)
            if not m:continue
            # Preserve source line verbatim; NBA injury PDF is multi-column,
            # so an unambiguous team+player cannot always be identified.
            rows.append({"page":page_no,"line":line_no,"raw":line.strip(),
                "status_mentioned":m.group(1).title(),"player_verified":False,
                "team_verified":False})
    return rows

def compile_report(snapshot,official=None,preview=None):
    official=official or {};preview=preview or {}
    text=official.get("raw_page_text",[])
    extracted=parse_lines(text)
    games={}
    for game in snapshot["predictions"]:
        gid=str(game["game_id"])
        previews=preview.get("games",{}).get(gid,{})
        games[gid]={"home_team":normalize_team(game["home_team"]),
          "away_team":normalize_team(game["away_team"]),
          "official_pdf_url":official.get("report_url"),
          "official_pdf_sha256":official.get("pdf_sha256"),
          "official_raw_status_lines":extracted,
          "official_player_team_status_confirmed":False,
          "espn_pregame_observations":previews.get("injury_observations",[]),
          "home_confirmed_starting_five":None,
          "away_confirmed_starting_five":None,
          "lineups_confirmed":False,
          "source_time_validated":False,
          "status":"pending_official_player_reconciliation_and_confirmed_lineups"}
    return {"games":games,"source_document_available":bool(official.get("official_document_retrieved")),
      "official_player_rows_resolved":0,"confirmed_starting_fives":0,
      "note":"No unsupported inference of NBA official player statuses or starting fives."}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--snapshot",required=True);ap.add_argument("--official")
    ap.add_argument("--preview");ap.add_argument("--output",required=True)
    a=ap.parse_args()
    load=lambda path:json.loads(Path(path).read_text()) if path and Path(path).is_file() else {}
    out=compile_report(load(a.snapshot),load(a.official),load(a.preview))
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x") as f:json.dump(out,f,indent=2)
    print(json.dumps({"games":len(out["games"]),"official_rows":len(next(iter(out["games"].values()))["official_raw_status_lines"]) if out["games"] else 0,"confirmed_starting_fives":0}))
