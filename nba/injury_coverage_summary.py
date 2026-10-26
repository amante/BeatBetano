"""Create a truthful NBA source-coverage scorecard from generated run artifacts."""
import argparse,json
from pathlib import Path

def summarize(official,joint,coverage):
    groups=joint.get("games",{})
    n=coverage.get("games")
    if type(n) is not int or n<0 or len(groups)!=n:raise ValueError("Slates disagree")
    candidate_games=sum(bool(g.get("official_structured_candidate_rows")) for g in groups.values())
    candidate_rows=sum(len(g.get("official_structured_candidate_rows",[])) for g in groups.values())
    source_eligible=sum(g.get("source_time_validated") is True for g in groups.values())
    confirmed_starters=sum(g.get("lineups_confirmed") is True for g in groups.values())
    return {"games":n,"official_pdf_retrieved":official.get("official_document_retrieved") is True,
      "official_pdf_error":official.get("retrieval_error_type"),
      "source_before_tip_games":source_eligible,
      "games_with_parsed_official_candidates":candidate_games,
      "parsed_official_candidate_rows":candidate_rows,
      "independently_verified_player_rows":0,
      "confirmed_starting_fives_games":confirmed_starters,
      "fully_verified_availability_games":coverage.get("complete_pregame_features",0),
      "previous_reference_games":9,"previous_reference_verified_availability_games":0,
      "independent_calibration_passed":False}
def markdown(r):
    lines=["### NBA injury and lineup evidence — actual run","","Metric | Value","--- | ---",
       f"Games | {r['games']}",
       f"NBA official PDF retrieved | {'yes' if r['official_pdf_retrieved'] else 'no'}",
       f"Official source retrieval error | {r['official_pdf_error'] or 'none reported'}",
       f"Games with pre-tip evidence | {r['source_before_tip_games']}",
       f"Games with parsed NBA injury rows | {r['games_with_parsed_official_candidates']}",
       f"Parsed injury row candidates | {r['parsed_official_candidate_rows']}",
       f"Independently verified player rows | {r['independently_verified_player_rows']}",
       f"Games with confirmed five starters on both sides | {r['confirmed_starting_fives_games']}",
       f"Games with complete verified availability | {r['fully_verified_availability_games']}",
       "", "Comparison baseline (earlier run): 0 of 9 games with complete verified availability.",
       "Parsed player rows are candidates only; do not equate them with verified injury or confirmed starters."]
    return "\n".join(lines)+"\n"
def main():
    ap=argparse.ArgumentParser()
    for key in ("official","joint","coverage","output","summary"):ap.add_argument("--"+key,required=True)
    a=ap.parse_args()
    load=lambda key:json.loads(Path(getattr(a,key)).read_text())
    report=summarize(load("official"),load("joint"),load("coverage"))
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2))
    md=Path(a.summary);md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text(markdown(report))
    print(json.dumps(report))
if __name__=="__main__":main()
