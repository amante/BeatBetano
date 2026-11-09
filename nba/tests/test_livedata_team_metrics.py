import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livedata_team_metrics import summarize_game


class LiveDataTests(unittest.TestCase):
    def test_final_overtime_boxscore_uses_total_turnovers_and_local_date(self):
        game_id = '0022600001'
        teams = [
            {'teamId': i, 'teamTricode': code, 'score': score, 'statistics': {
                'fieldGoalsAttempted': 90, 'freeThrowsAttempted': 20,
                'reboundsOffensive': 10, 'turnoversTotal': 15, 'turnovers': 13, 'points': score}}
            for i, code, score in ((1, 'AAA', 110), (2, 'BBB', 109))]
        game = {'gameId': game_id, 'gameStatus': 3, 'gameTimeUTC': '2026-11-09T01:00:00Z',
                'period': 5, 'regulationPeriods': 4, 'homeTeam': teams[0], 'awayTeam': teams[1]}
        result = summarize_game({'game': game}, game_id, date(2026, 11, 8))
        self.assertEqual(result['regulation_and_overtime_minutes'], 53)
        self.assertAlmostEqual(result['teams'][0]['possessions_estimated'], 103.8)
        with self.assertRaisesRegex(ValueError, 'after requested cutoff'):
            summarize_game({'game': game}, game_id, date(2026, 11, 7))
        game['gameStatus'] = 2
        with self.assertRaisesRegex(ValueError, 'final boxscore'):
            summarize_game({'game': game}, game_id, date(2026, 11, 8))
