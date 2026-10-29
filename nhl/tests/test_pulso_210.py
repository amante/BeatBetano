import unittest
from unittest.mock import patch
from nhl.pulso_calibration_segments_210 import diagnostics
class Tests(unittest.TestCase):
 def test_perfect_calibration_in_two_groups(self):
  rows=[]
  for i in range(100):
   p=0.2 if i<50 else 0.8
   y="home" if (i%5)<(1 if i<50 else 4) else "away"
   rows.append({"date":"2026-03-01","y":{"ml":y},"probs":{"ml":[p,1-p]}})
  with patch("nhl.pulso_calibration_segments_210.CATEGORIES",{"ml":("home","away")}):
   report=diagnostics(rows,min_bin=25)
  self.assertEqual(report["n"],100)
  self.assertEqual(report["markets"]["ml"]["classes"]["home"]["class_event_count"],50)
  self.assertFalse(report["promotion"])
 def test_empty_rejected(self):
  with self.assertRaises(ValueError):diagnostics([])
if __name__=="__main__":unittest.main()
