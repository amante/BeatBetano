import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_epa import build

class TestEPA(unittest.TestCase):
    def test_no_same_day_leakage(self):
        games=pd.DataFrame([
            dict(game_id="g1",season=2023,gameday="2023-09-01",home_team="A",away_team="B",home_score=28,away_score=7),
            dict(game_id="g2",season=2023,gameday="2023-09-01",home_team="A",away_team="C",home_score=7,away_score=28),
            dict(game_id="g3",season=2023,gameday="2023-09-08",home_team="B",away_team="A",home_score=10,away_score=14)])
        plays=[]
        for gid,home,away in [("g1","A","B"),("g2","A","C"),("g3","B","A")]:
            plays.extend([dict(game_id=gid,posteam=home,defteam=away,epa=.3,success=1,play_type="pass"),
                          dict(game_id=gid,posteam=away,defteam=home,epa=-.2,success=0,play_type="run")])
        pbp=pd.DataFrame(plays)
        a=build(games,pbp)
        changed=pbp.copy()
        changed.loc[changed.game_id=="g1","epa"]=8
        b=build(games,changed)
        self.assertEqual(a.iloc[1].off_epa_diff,b.iloc[1].off_epa_diff)
        self.assertNotEqual(a.iloc[2].off_epa_diff,b.iloc[2].off_epa_diff)
if __name__=="__main__":unittest.main()
