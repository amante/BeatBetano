import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from build_forecast_index import build
from multisport.daily_forecasts import publish
from multisport.tests.test_forecast_revisions import source


def publish_pregame(sport, report, directory):
    # Simulate emission at the fixture cutoff, independent of the CI runner date.
    emitted = datetime.fromisoformat(report['as_of_utc'].replace('Z', '+00:00'))
    with patch('multisport.forecast_revisions.datetime') as clock:
        clock.now.return_value = emitted
        return publish(sport, report, directory)


class ForecastIndexTests(unittest.TestCase):
    def test_initial_and_update_are_preserved_without_certified_picks(self):
        with tempfile.TemporaryDirectory() as d:
            s=source('nba');publish_pregame('nba',s,d)
            s=source('nba',.6,'2026-11-06T11:00:00Z');publish_pregame('nba',s,d)
            result=build(d);e=result['events'][0]
            self.assertFalse(result['errors'])
            self.assertEqual(e['initial']['probabilities']['home'],.55)
            self.assertEqual(e['latest']['probabilities']['home'],.6)
            self.assertAlmostEqual(e['delta']['home'],.05)
            self.assertEqual(len(e['history']),2)
            self.assertEqual(e['selection_status'],'PASS')
            self.assertFalse(e['calibration_certified'])

    def test_tampered_latest_never_falls_back_to_old_percentages(self):
        with tempfile.TemporaryDirectory() as d:
            s=source('nba');publish_pregame('nba',s,d)
            s=source('nba',.6,'2026-11-06T11:00:00Z');publish_pregame('nba',s,d)
            path=next(Path(d).glob('*/*/000002.json'));data=json.loads(path.read_text())
            data['events'][0]['forecast']['probabilities']['home']=.9
            path.write_text(json.dumps(data))
            result=build(d)
            self.assertFalse(result['events'])
            self.assertEqual(len(result['errors']),1)

    def test_missing_archive_and_soccer_three_way(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(build(Path(d)/'missing')['archive_present'])
            publish_pregame('soccer',source('soccer'),d)
            e=build(d)['events'][0]
            self.assertEqual(set(e['initial']['probabilities']),{'home','draw','away'})
            self.assertTrue(all(v==0 for v in e['delta'].values()))
