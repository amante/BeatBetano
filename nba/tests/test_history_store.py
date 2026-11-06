import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from history_store import daily_delta, frozen_history


class HistoryStoreTests(unittest.TestCase):
    def test_frozen_three_seasons_need_no_network(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Network forbidden')):
            rows,audit=frozen_history()
        self.assertEqual(len(rows),3690)
        self.assertEqual(audit['network_requests'],0)

    def test_repeated_run_fetches_only_next_missing_day_including_empty_days(self):
        with tempfile.TemporaryDirectory() as root:
            with patch('history_store.fetch_range',return_value=([],0,{})) as fetch:
                _,a=daily_delta(root,'2026-10-20','2026-10-21')
                self.assertEqual(fetch.call_count,2)
                _,b=daily_delta(root,'2026-10-20','2026-10-21')
                self.assertEqual(fetch.call_count,2)
                _,c=daily_delta(root,'2026-10-20','2026-10-22')
                self.assertEqual(fetch.call_count,3)
                self.assertEqual(c['requested_dates'],['2026-10-22'])
                self.assertEqual(b['network_requests'],0)
                self.assertEqual(len(c['reused_dates']),2)

    def test_gaps_are_fetched_but_cached_future_days_do_not_leak(self):
        with tempfile.TemporaryDirectory() as root:
            with patch('history_store.fetch_range',return_value=([],0,{})):
                daily_delta(root,'2026-10-20','2026-10-22')
                Path(root,'2026-10-21.json').unlink()
                _,audit=daily_delta(root,'2026-10-20','2026-10-21')
            self.assertEqual(audit['requested_dates'],['2026-10-21'])
            self.assertEqual(audit['reused_dates'],['2026-10-20'])

    def test_corrupted_cache_does_not_trigger_full_redownload(self):
        with tempfile.TemporaryDirectory() as root:
            with patch('history_store.fetch_range',return_value=([],0,{})) as fetch:
                daily_delta(root,'2026-10-20','2026-10-20')
                p=Path(root,'2026-10-20.json');d=json.loads(p.read_text());d['raw_events']=9
                p.write_text(json.dumps(d))
                with self.assertRaisesRegex(ValueError,'integrity'):daily_delta(root,'2026-10-20','2026-10-20')
                self.assertEqual(fetch.call_count,1)

    def test_incomplete_or_failed_day_never_advances_cache(self):
        with tempfile.TemporaryDirectory() as root:
            metadata={'1':{'season':{'type':2},'competitions':[{'status':{'completed':False}}]}}
            with patch('history_store.fetch_range',return_value=([],1,metadata)):
                with self.assertRaisesRegex(ValueError,'Incomplete'):daily_delta(root,'2026-10-20','2026-10-20')
            self.assertFalse(list(Path(root).iterdir()))
            with patch('history_store.fetch_range',side_effect=RuntimeError('offline')):
                with self.assertRaises(RuntimeError):daily_delta(root,'2026-10-20','2026-10-20')
            self.assertFalse(list(Path(root).iterdir()))

    def test_conflicting_duplicate_id_rejected(self):
        row={'game_id':'1','tipoff_utc':'2026-10-20T23:00:00Z','home_points':100}
        with tempfile.TemporaryDirectory() as root:
            with patch('history_store.fetch_range',side_effect=[([row],1,{}),([{**row,'home_points':101}],1,{})]):
                with self.assertRaisesRegex(ValueError,'Conflicting'):daily_delta(root,'2026-10-20','2026-10-21')
