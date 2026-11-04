import unittest
from unittest.mock import patch
import nhl.joint_match_input_builder_321 as builder

class BuilderTests(unittest.TestCase):
    def test_season_uses_nhl_season_boundary(self):
        self.assertEqual(builder.season_for('2026-11-03'),'20262027')
        self.assertEqual(builder.season_for('2027-03-01'),'20262027')
        self.assertEqual(builder.season_for('2027-07-01'),'20272028')

    def test_toi_parses_official_clock_and_seconds(self):
        self.assertAlmostEqual(builder.toi('17:30'),17.5)
        self.assertAlmostEqual(builder.toi(1050),17.5)
        with self.assertRaises(ValueError): builder.toi('17:60')

    def test_paginated_stats_requires_exact_total(self):
        responses=[({'total':2,'data':[{'playerId':1},{'playerId':2}]},{'url':'x','sha256':'a'*64,'retrieved_at_utc':'2026-11-01T00:00:00Z'})]
        with patch.object(builder,'get_json',side_effect=responses) as get:
            rows,sources=builder.stat_rows('skater/summary','20262027','2026-11-03')
        self.assertEqual([r['playerId'] for r in rows],[1,2])
        self.assertEqual(len(sources),1)
        with patch.object(builder,'get_json',side_effect=[({'total':3,'data':[{'playerId':1},{'playerId':2}]},responses[0][1]),({'total':3,'data':[]},responses[0][1])]):
            with self.assertRaisesRegex(ValueError,'Incomplete'):
                builder.stat_rows('skater/summary','20262027','2026-11-03')

if __name__=='__main__': unittest.main()
