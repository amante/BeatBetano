import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from matchup_reconciliation import reconcile

S={"sport":"nfl","as_of_utc":"2026-10-29T12:00:00Z","events":[
{"event_id":"123","start_utc":"2026-10-30T00:00:00Z","home_team":"SEA","away_team":"KC"}]}
class Tests(unittest.TestCase):
    def test_empty_unverified_is_not_injury_impact(self):
        g=reconcile(S,{"games":[]})["games"][0]
        self.assertEqual(g["confirmed_secondary_inactives"],[])
        self.assertIsNone(g["winner_log_odds_adjustment"])
    def test_official_inactive(self):
        player={"player_id":"1","team":"KC","position":"CB","status":"inactive",
        "observed_at_utc":"2026-10-29T11:00:00Z","source_url":"https://nfl.com/1",
        "source_is_official":True}
        x=reconcile(S,{"games":[]},{"games":[{"event_id":"123","players":[player]}]})
        self.assertEqual(len(x["games"][0]["confirmed_secondary_inactives"]),1)
    def test_reject_future_and_unofficial(self):
        player={"player_id":"1","team":"KC","position":"CB","status":"inactive",
        "observed_at_utc":"2026-10-29T13:00:00Z","source_url":"https://nfl.com/1",
        "source_is_official":True}
        x=reconcile(S,{"games":[]},{"games":[{"event_id":"123","players":[player]}]})
        self.assertEqual(len(x["games"][0]["verified_players"]),0)
        player["observed_at_utc"]="2026-10-29T11:00:00Z"
        player["source_is_official"]=False
        x=reconcile(S,{"games":[]},{"games":[{"event_id":"123","players":[player]}]})
        self.assertFalse(x["games"][0]["verified_players"][0]["official_inactive_confirmed"])
    def test_weather_requires_provenance(self):
        x=reconcile(S,{"games":[]},{"games":[{"event_id":"123","weather":{"wind_mph":20}}]})
        self.assertIsNone(x["games"][0]["weather_forecast"])
if __name__=="__main__":unittest.main()
