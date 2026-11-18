import unittest
from datetime import datetime, timedelta, timezone

from nhl.prospective_capture_window import active_capture_window


class ProspectiveCaptureWindowTests(unittest.TestCase):
    def test_two_hour_start_survives_delayed_workflow_and_stops_at_last_start(self):
        first=datetime(2026,11,17,0,30,tzinfo=timezone.utc)
        last=datetime(2026,11,17,2,30,tzinfo=timezone.utc)
        self.assertFalse(active_capture_window(first-timedelta(hours=2,seconds=1),[first,last]))
        self.assertTrue(active_capture_window(first-timedelta(hours=2),[first,last]))
        # A scheduled run delayed 7 minutes across the :30 boundary still captures.
        self.assertTrue(active_capture_window(first-timedelta(hours=1,minutes=53),[first,last]))
        self.assertTrue(active_capture_window(first-timedelta(minutes=1),[first,last]))
        self.assertFalse(active_capture_window(last,[first,last]))

    def test_empty_slate_is_inactive_and_naive_time_is_rejected(self):
        now=datetime(2026,11,17,0,0,tzinfo=timezone.utc)
        self.assertFalse(active_capture_window(now,[]))
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            active_capture_window(datetime(2026,11,17),[now])


if __name__ == "__main__":
    unittest.main()
