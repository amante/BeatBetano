import unittest,sys,csv,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from historical_target_walkforward import outcomes,timeline,metrics,season,read_labels
class TargetWalkforwardTests(unittest.TestCase):
 def rows(self):
  return [{"date":"2025-10-10","game_id":"1","home":"A","away":"B","ml_winner":"home","rt_result":"home","first_to_plus3":"home","home_reached_plus3":"True","away_reached_plus3":"False"},
          {"date":"2025-10-10","game_id":"2","home":"A","away":"C","ml_winner":"away","rt_result":"draw","first_to_plus3":"None","home_reached_plus3":"False","away_reached_plus3":"False"},
          {"date":"2025-10-11","game_id":"3","home":"A","away":"B","ml_winner":"home","rt_result":"draw","first_to_plus3":"away","home_reached_plus3":"False","away_reached_plus3":"True"}]
 def test_csv_empty_first3_is_not_missing(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   file=Path(tmp)/"labels.csv"
   rows=[self.rows()[0],self.rows()[1],self.rows()[2]]
   rows[1]["first_to_plus3"]=""
   with file.open("w",newline="") as handle:
    writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
   with patch("historical_target_walkforward.Path",wraps=Path):
    with self.assertRaisesRegex(ValueError,"Expected 2811"):read_labels(file)
  self.assertEqual(outcomes(rows[1])["first3"],"none")
 def test_targets(self):
  self.assertEqual(outcomes(self.rows()[1])["first3"],"none")
 def test_same_date_never_observes_other_game(self):
  seq=timeline(self.rows(),20,1)
  self.assertEqual(seq[0]["probs"],seq[1]["probs"])
 def test_future_outcome_change_does_not_change_own_prediction(self):
  a=self.rows();base=timeline(a,20,1)[2]["probs"]
  a[2]["ml_winner"]="away"
  self.assertEqual(base,timeline(a,20,1)[2]["probs"])
 def test_probability_metrics(self):
  out=metrics(timeline(self.rows(),20,1))
  self.assertEqual(set(out),{"ml","rt","first3","home3","away3"})
  self.assertTrue(all(x["n"]==3 for x in out.values()))
if __name__=="__main__":unittest.main()
