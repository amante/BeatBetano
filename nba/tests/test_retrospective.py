import sys,unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import retrospective
class Tests(unittest.TestCase):
    def test_cutoff_rejects_non_midnight(self):
        with TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,"00:00 UTC"):
                retrospective.retrospective("2026-10-24",d,"2026-10-24T12:00:00Z")
    def test_final_score_not_used_as_model_input(self):
        final={"game_id":"fin","season":2027,"tipoff_utc":"2026-10-24T20:00:00Z",
               "home_team":"BOS","away_team":"NYK","home_points":110,"away_points":98}
        base={"game_id":"prior","season":2026,"tipoff_utc":"2026-04-01T00:00:00Z",
              "home_team":"BOS","away_team":"NYK","home_points":101,"away_points":98}
        def fake_build(path,*args):
            Path(path).write_text(__import__("json").dumps([base]))
            return {"source_count":1}
        with TemporaryDirectory() as d,patch.object(retrospective,"build",side_effect=fake_build),patch.object(retrospective,"fetch_range",return_value=([final],1,{})):
            snap,metrics=retrospective.retrospective("2026-10-24",d)
        self.assertEqual(snap["predictions"][0]["game_id"],"fin")
        self.assertEqual(metrics["settled_games"],1)
        self.assertEqual(metrics["replay_method"],"RETROSPECTIVE_SIMULATION_NOT_ORIGINAL_PREGAME")
if __name__=="__main__":unittest.main()
