"""Map timestamped ESPN injury claims to current player IDs without upgrading reliability.

Only unambiguous team+normalized-name matches are passed to roster resolver.
Unknown players and conflicting claims are reported. Missing injury reports do
not certify that unmentioned players are available.
"""
import argparse,json,unicodedata
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from team_identity import same_team
from official_injury_table import extract as extract_official_rows
from official_injury_table import extract_team_submissions

def normalize(s):
 return " ".join("".join(c for c in unicodedata.normalize("NFKD",str(s).casefold()) if not unicodedata.combining(c)).split())
def utc(s):
 try:
  d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
  return d.astimezone(timezone.utc) if d.tzinfo else None
 except (ValueError,TypeError):return None
def status(s):
 t=normalize(s)
 if t in ("out","inactive","suspended","ruled out"):return "out"
 if t in ("questionable","doubtful","day-to-day","day to day"):return "questionable"
 if t=="probable":return "probable"
 # Do not infer active from absence of an injury entry.
 return None
def official_status(s):
 t=normalize(s)
 if t in ("out","inactive","suspended","ruled out"):return "out"
 if t=="questionable":return "questionable"
 if t=="doubtful":return "doubtful"
 if t=="probable":return "probable"
 if t in ("available","active"):return "available"
 return None
def game_day(tipoff):
 value=utc(tipoff)
 return value.astimezone(ZoneInfo("America/New_York")).date().isoformat() if value else None
def report_game_day(value):
 try:return datetime.strptime(str(value),"%m/%d/%Y").date().isoformat()
 except (TypeError,ValueError):return str(value or "")
def matchup_matches(row,game):
 matchup=str(row.get("matchup") or "").upper().split("@")
 if len(matchup)!=2:return True
 expected={game["home_team"],game["away_team"]}
 return all(any(same_team(code,team) for team in expected) for code in matchup)
def official_rows_for_game(game,official):
 """Return rows for one fixture and expose each scope-filter count."""
 diagnostic={"game_id":str(game.get("game_id")),"status":"not_evaluated",
  "source_rows":0,"date_rows":0,"date_and_matchup_rows":0,"fixture_team_rows":0}
 if official.get("official_document_retrieved") is not True:
  diagnostic["status"]="report_not_retrieved"
  return [],[],diagnostic
 report_time=utc(official.get("source_report_as_of_utc"))
 downloaded=utc(official.get("downloaded_at_utc"))
 tip=utc(game.get("tipoff_utc"))
 if not report_time or not downloaded or not tip or not report_time<=downloaded<tip:
  diagnostic["status"]="report_time_not_pregame"
  return [],[],diagnostic
 rows=official.get("structured_player_rows")
 if not isinstance(rows,list):
  try:rows=extract_official_rows(official.get("raw_page_text",[]),continuous_table=True)
  except ValueError:rows=extract_official_rows(official.get("raw_page_text",[]))
 submissions=official.get("team_report_statuses")
 if not isinstance(submissions,list):submissions=extract_team_submissions(official.get("raw_page_text",[]))
 diagnostic["source_rows"]=len(rows)
 expected_day=game_day(game.get("tipoff_utc"))
 teams={game["home_team"],game["away_team"]}
 date_rows=[row for row in rows if report_game_day(row.get("game_date"))==expected_day]
 diagnostic["date_rows"]=len(date_rows)
 matchup_rows=[row for row in date_rows if matchup_matches(row,game)]
 diagnostic["date_and_matchup_rows"]=len(matchup_rows)
 relevant=[row for row in matchup_rows
           if any(same_team(row.get("team"),team) for team in teams)]
 diagnostic["fixture_team_rows"]=len(relevant)
 diagnostic["status"]="rows_selected" if relevant else "no_rows_for_fixture"
 pending=[row for row in submissions
          if report_game_day(row.get("game_date"))==expected_day
          and matchup_matches(row,game)
          and any(same_team(row.get("team"),team) for team in teams)]
 return relevant,pending,diagnostic
def reconcile(snapshot,roster,sporting,official=None):
 official_provided=official is not None
 official=official or {}
 digest=snapshot["content_sha256"]
 if roster.get("snapshot_sha256")!=digest:raise ValueError("Roster snapshot mismatch")
 output={};unknown=[];conflicts=[];official_unmatched=[];official_matched=0;pending_teams=[];official_diagnostics=[]
 for game in snapshot["predictions"]:
  gid=str(game["game_id"]);tip=utc(game["tipoff_utc"]);per_team={}
  evidence=sporting.get("games",{}).get(gid,{}).get("supplementary_injury_observations",{})
  observed=utc(evidence.get("observed_at_utc"))
  rows=evidence.get("items",[])
  if not isinstance(rows,list):rows=[]
  source=evidence.get("source")
  valid_time=bool(tip and observed and observed<tip)
  report_time=utc(official.get("source_report_as_of_utc"))
  downloaded=utc(official.get("downloaded_at_utc"))
  official_time_valid=bool(official.get("official_document_retrieved") is True and tip and report_time and downloaded and report_time<=downloaded<tip)
  official_rows,pending,official_diag=official_rows_for_game(game,official)
  if not official_time_valid and official_diag["status"]=="not_evaluated":
   official_diag["status"]="report_time_not_pregame"
  official_diagnostics.append(official_diag)
  for row in pending:
   pending_teams.append({"game_id":gid,"team":row.get("team"),"game_date":row.get("game_date"),"matchup":row.get("matchup"),"status":"not_yet_submitted","source_url":official.get("report_url"),"observed_at_utc":official.get("downloaded_at_utc")})
  for team in (game["home_team"],game["away_team"]):
   members=roster.get("games",{}).get(gid,{}).get("teams",{}).get(team,{}).get("players",[])
   by_name={}
   for p in members:
    if p.get("player_id") and p.get("player"):
     by_name.setdefault(normalize(p["player"]),[]).append(str(p["player_id"]))
   member_ids={str(p["player_id"]) for p in members if p.get("player_id")}
   claims={}
   for row in rows if valid_time and source else []:
    if not same_team(row.get("team"),team):continue
    reported=utc(row.get("reported_at_utc")) if row.get("reported_at_utc") else None
    if row.get("reported_at_utc") and (not reported or reported>observed):continue
    state=status(row.get("status"))
    if state is None:continue
    source_id=str(row.get("player_id") or "")
    ids=[source_id] if source_id and source_id in member_ids else by_name.get(normalize(row.get("player")),[]) if not source_id else []
    if len(ids)!=1:
     unknown.append({"game_id":gid,"team":team,"player":row.get("player"),"reason":"not_unique_roster_match"})
     continue
    pid=ids[0]
    claims.setdefault(pid,[]).append({"player_id":pid,"status":state,
     "source_url":source,"observed_at_utc":evidence["observed_at_utc"],
     "identity_match":"provider_id" if source_id else "unique_normalized_name",
     "reported_at_utc":row.get("reported_at_utc"),
     "confidence":"supplementary_espn_injury_claim_not_official"})
   for row in official_rows:
    if not same_team(row.get("team"),team):continue
    state=official_status(row.get("status"))
    ids=by_name.get(normalize(row.get("player")),[])
    if state is None or len(ids)!=1:
     official_unmatched.append({"game_id":gid,"team":team,"player":row.get("player"),
       "status":row.get("status"),"reason":"unsupported_status" if state is None else "not_unique_roster_match",
       "source_url":official.get("report_url"),"report_as_of_utc":official.get("source_report_as_of_utc")})
     continue
    pid=ids[0];official_matched+=1
    claims.setdefault(pid,[]).append({"player_id":pid,"status":state,
     "source_url":official.get("report_url"),"observed_at_utc":official["downloaded_at_utc"],
     "identity_match":"unique_normalized_name_within_team_roster",
     "reported_at_utc":official.get("source_report_as_of_utc"),
     "confidence":"official_nba_injury_report_unique_roster_match",
     "official_row":{"game_date":row.get("game_date"),"matchup":row.get("matchup"),
       "page":row.get("page"),"line":row.get("line"),"raw":row.get("raw")}})
   for pid,observations in claims.items():
    if len({x["status"] for x in observations})>1:
     conflicts.append({"game_id":gid,"team":team,"player_id":pid})
   per_team[team]=[item for values in claims.values() for item in values]
  output[gid]={"teams":per_team}
 result={"snapshot_sha256":digest,"games":output,"unmatched_claims":unknown,
  "conflicts":conflicts,"source_reliability":"supplementary_not_official",
  "does_not_confirm_active_players":True,"no_odds_input":True}
 if official_provided:
  result.update({"official_unmatched_claims":official_unmatched,
   "official_matched_claims":official_matched,
   "official_structured_candidate_rows":len(official.get("structured_player_rows",[])),
   "official_rows_by_fixture":official_diagnostics,
   "official_rows_for_fixtures":sum(x["fixture_team_rows"] for x in official_diagnostics),
   "official_report_retrieved":official.get("official_document_retrieved") is True,
   "official_report_as_of_utc":official.get("source_report_as_of_utc"),
   "official_team_reports_not_submitted":pending_teams,
   "source_reliability":"official_nba_pdf_plus_supplementary_espn" if official_matched else ("official_rows_unmatched" if sum(x["fixture_team_rows"] for x in official_diagnostics) else "supplementary_not_official")})
 return result
def main():
 p=argparse.ArgumentParser()
 for name in ("snapshot","roster","sporting","output"):p.add_argument("--"+name,required=True)
 p.add_argument("--official")
 args=p.parse_args();snap=json.loads(Path(args.snapshot).read_text())
 def read(path):return json.loads(Path(path).read_text()) if path and Path(path).exists() else {}
 report=reconcile(snap,read(args.roster),read(args.sporting),read(args.official))
 out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2))
 print(json.dumps({"games":len(report["games"]),"matched_status_claims":sum(len(x) for g in report["games"].values() for x in g["teams"].values()),"official_matched":report["official_matched_claims"],"official_unmatched":len(report["official_unmatched_claims"]),"unmatched":len(report["unmatched_claims"])}))
if __name__=="__main__":main()
