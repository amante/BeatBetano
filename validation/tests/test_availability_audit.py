import sys,tempfile,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from availability_audit import audit

class AuditTests(unittest.TestCase):
    def test_missing_away_team_excluded_and_coverage_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            pd.DataFrame([{"game_id":"G1","season":2024,"home_team":"H","away_team":"A"},
                          {"game_id":"G2","season":2024,"home_team":"H","away_team":"B"}]).to_csv(p/"games.csv",index=False)
            def row(game,team,player):
                return {"game_id":game,"team":team,"player_id":player,"position":"CB","status":"OUT",
                        "snapshot_utc":"2024-09-07T13:00:00Z",
                        "kickoff_utc":"2024-09-08T17:00:00Z","source":"fixture"}
            pd.DataFrame([row("G1","H","p1"),row("G1","A","p2"),row("G2","H","p3")]).to_csv(p/"reports.csv",index=False)
            result=audit(p/"games.csv",p/"reports.csv",p/"out")
            self.assertEqual(result["matched_games"],1)
            self.assertEqual(result["coverage_pct"],50.)
            self.assertEqual(result["status"],"coverage_audit_only_no_predictive_validation")
if __name__=="__main__":unittest.main()
