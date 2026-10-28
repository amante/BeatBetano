import unittest
from nhl.nhlcom_projected_lineup_capture import extract
class NHLEditorialLinesTests(unittest.TestCase):
 def test_capture_editorial_projection_without_inventing_confirmation(self):
  html="""<html><body><h2>Bruins projected lineup</h2><p>A -- B -- C</p><p>D -- E</p><p>Jeremy Swayman</p><p>Scratched: X, Y</p><p>Injured: None</p><p>Status report</p><h2>Hurricanes projected lineup</h2><p>F -- G -- H</p><p>Injured: John Smith (lower body)</p><p>Status report</p></body></html>"""
  x=extract(html)
  self.assertEqual(len(x),2)
  self.assertEqual(x[0]["lineup_type"],"projected")
  self.assertEqual(x[0]["scratched"],["X","Y"])
  self.assertEqual(x[0]["injured"],[])
  self.assertEqual(x[1]["injured"],["John Smith (lower body)"])
 def test_refuse_unknown_format(self):
  with self.assertRaisesRegex(ValueError,"Unrecognized"):
   extract("<html><body>No team lineups here</body></html>")
if __name__=="__main__":unittest.main()
