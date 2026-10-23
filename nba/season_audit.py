"""Audit NBA regular-season scoreboard classification without guessing removals."""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path

def audit(games):
    seasons=defaultdict(list)
    for g in games:
        seasons[int(g["season"])].append(g)
    output={}
    for year,rows in sorted(seasons.items()):
        appearances=Counter()
        for g in rows:
            appearances[g["home_team"]]+=1
            appearances[g["away_team"]]+=1
        over={t:n-82 for t,n in sorted(appearances.items()) if n>82}
        under={t:82-n for t,n in sorted(appearances.items()) if n<82}
        incident_teams=set(over)|set(under)
        candidates=[{"game_id":str(g["game_id"]),"date":g["tipoff_utc"],
                     "home":g["home_team"],"away":g["away_team"]}
                    for g in rows if g["home_team"] in incident_teams or g["away_team"] in incident_teams]
        output[str(year)]={"games":len(rows),"expected_regular_games":1230,
                           "count_difference":len(rows)-1230,
                           "team_appearances":dict(sorted(appearances.items())),
                           "team_over_82":over,"team_under_82":under,
                           "candidate_games_requiring_source_review":candidates,
                           "coverage_verified":len(rows)==1230 and len(appearances)==30 and not over and not under}
    return output

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    args=p.parse_args()
    rows=json.loads(Path(args.input).read_text())
    report=audit(rows)
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2))
    print(json.dumps({year:{k:v for k,v in data.items() if k not in ("candidate_games_requiring_source_review","team_appearances")} for year,data in report.items()},indent=2))
