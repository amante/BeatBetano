import unittest
from datetime import date

from multisport.daily_pipeline import nba_history_window


class NBAHistoryWindowTests(unittest.TestCase):
    def test_utc_midnight_does_not_close_current_league_day(self):
        history = [{'tipoff_utc': '2026-11-05T02:00:00Z'}]
        start, end = nba_history_window(history, '2026-11-10T00:02:20Z')
        self.assertEqual(start, date(2026, 11, 4))
        self.assertEqual(end, date(2026, 11, 8))
