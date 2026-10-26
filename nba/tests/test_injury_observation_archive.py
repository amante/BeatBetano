import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from injury_observation_archive import archive

def snap():
    return {"content_sha256":"hash","created_at_utc":"2026-10-25T15:00:00Z",
        "predictions":[{"game_id":"1","home_team":"BOS","away_team":"NYK",
                        "tipoff_utc":"2026-10-25T19:00:00Z"}]}
def sporting():
    return {"games":{"1":{"supplementary_injury_observations":{
      "source":"https://site.api.espn.com/injuries",
      "observed_at_utc":"2026-10-25T14:59:00Z",
      "items":[{"team":"BOS","player":"A","status":"Out"}]}}}}

class TestArchive(unittest.TestCase):
    def test_preserves_but_never_certifies(self):
        x=archive(snap(),sporting())
        self.assertEqual(x["observation_count"],1)
        self.assertFalse(x["impact_training_authorized"])
        self.assertFalse(x["games"][0]["observations"][0]["officially_verified"])
    def test_reject_future_observation(self):
        s=sporting()
        s["games"]["1"]["supplementary_injury_observations"]["observed_at_utc"]="2026-10-25T16:00:00Z"
        x=archive(snap(),s)
        self.assertEqual(x["observation_count"],0)
        self.assertIn("sporting_injury_source_not_point_in_time",x["games"][0]["issues"])
    def test_reject_wrong_team(self):
        s=sporting()
        s["games"]["1"]["supplementary_injury_observations"]["items"][0]["team"]="LAL"
        self.assertEqual(archive(snap(),s)["observation_count"],0)
    def test_reject_post_tipoff_snapshot(self):
        s=snap();s["created_at_utc"]="2026-10-25T20:00:00Z"
        with self.assertRaises(ValueError):archive(s,sporting())
    def test_wrong_preview_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            archive(snap(),sporting(),{"snapshot_sha256":"incorrect"})

if __name__=="__main__":unittest.main()
