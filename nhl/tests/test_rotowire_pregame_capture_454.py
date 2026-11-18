import unittest
from nhl.rotowire_pregame_capture_454 import build, parse_cards

HTML = b"""
<div class="lineup__box">
  <div class="lineup__team is-visit"><div class="lineup__abbr">BOS</div><div>Bruins</div></div>
  <div class="lineup__team is-home"><div class="lineup__abbr">NYR</div><div>Rangers</div></div>
  <div class="lineup__main"><ul class="lineup__list is-visit"><li class="lineup__player">Goalie A Confirmed</li></ul>
  <ul class="lineup__list is-home"><li class="lineup__player">Goalie B Likely</li></ul></div>
</div>
"""

class RotoWireCaptureTests(unittest.TestCase):
    def test_extracts_fixture_card_and_keeps_it_non_predictive(self):
        report = {"games": [{
            "game_id": 2026020001, "away": "BOS", "home": "NYR",
            "start_utc": "2026-11-18T00:00:00Z",
        }]}
        result = build(HTML, report, "2026-11-17T20:00:00Z")
        self.assertEqual(len(result["games"]), 1)
        self.assertEqual(result["games"][0]["game_id"], "2026020001")
        self.assertIn("Confirmed", result["games"][0]["source_observation"])
        self.assertFalse(result["games"][0]["probabilities_modified"])
        self.assertFalse(result["official"])

    def test_cards_without_fixture_match_are_preserved_as_unmatched(self):
        report = {"games": []}
        result = build(HTML, report, "2026-11-17T20:00:00Z")
        self.assertEqual(len(result["games"]), 0)
        self.assertEqual(len(result["unmatched_cards"]), 1)

    def test_page_layout_change_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "no lineup cards"):
            parse_cards(b"<html><body>maintenance</body></html>")

if __name__ == "__main__":
    unittest.main()
