import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fetch_nfl_injuries import normalize

class InjurySourceTests(unittest.TestCase):
    def test_only_pregame_records_survive(self):
        games=pd.DataFrame([{"game_id":"2024_01_A_B","season":2024,"week":1,
            "home_team":"A","away_team":"B","gameday":"2024-09-08","gametime":"13:00"}])
        def report(team,ident,date):
            return {"season":2024,"week":1,"team":team,"gsis_id":ident,"position":"CB",
                    "report_status":"Out","date_modified":date}
        reports=pd.DataFrame([report("A","p1","2024-09-07T19:00:00Z"),
          report("B","p2","2024-09-08T18:00:00Z")])
        result=normalize(games,reports)
        self.assertEqual(len(result),1)
        self.assertEqual(result.iloc[0].team,"A")
    def test_missing_timestamp_not_backfilled(self):
        games=pd.DataFrame([{"game_id":"g","season":2024,"week":1,"home_team":"A",
          "away_team":"B","gameday":"2024-09-08","gametime":"13:00"}])
        reports=pd.DataFrame([{"season":2024,"week":1,"team":"A","gsis_id":"p",
          "position":"CB","report_status":"Out","date_modified":None}])
        self.assertTrue(normalize(games,reports).empty)

if __name__=="__main__":unittest.main()
