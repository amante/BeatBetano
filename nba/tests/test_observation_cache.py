import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import player_game_history
import possession_intelligence
from observation_cache import read, save

GAME={'game_id':'123','tipoff_utc':'2026-10-20T00:00:00Z','home_team':'H','away_team':'A'}

class ObservationCacheTests(unittest.TestCase):
    def test_player_second_run_preserves_original_observation_without_request(self):
        client=Mock()
        players=[{'game_id':'123','observed_at_utc':'2026-10-21T00:00:00Z'}]
        with tempfile.TemporaryDirectory() as root:
            with patch.object(player_game_history,'parse_boxscore',return_value=players):
                first=player_game_history.collect([GAME],session=client,cache_dir=root)
                second=player_game_history.collect([GAME],session=client,cache_dir=root)
            self.assertEqual(client.get.call_count,1)
            self.assertEqual(first['players'],second['players'])

    def test_team_second_run_and_new_game_delta(self):
        client=Mock()
        stats={'H':{'points':100,'possessions_estimated':100},'A':{'points':99,'possessions_estimated':100}}
        with tempfile.TemporaryDirectory() as root:
            with patch.object(possession_intelligence,'extract',return_value=stats):
                first=possession_intelligence.capture([GAME],session=client,cache_dir=root)
                second=possession_intelligence.capture([GAME],session=client,cache_dir=root)
                third=possession_intelligence.capture([GAME,{**GAME,'game_id':'124'}],session=client,cache_dir=root)
            self.assertEqual(client.get.call_count,2)
            self.assertEqual(first['games'],second['games'])
            self.assertEqual(len(third['games']),4)

    def test_corruption_or_changed_fixture_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            save(root,GAME,[])
            with self.assertRaises(ValueError):read(root,{**GAME,'away_team':'B'})
            p=Path(root,'123.json');r=json.loads(p.read_text());r['data']=[1];p.write_text(json.dumps(r))
            with self.assertRaises(ValueError):read(root,GAME)
