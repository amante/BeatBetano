import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livedata_team_metrics import bind_history, summarize_game


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

    def test_crosswalk_requires_unique_exact_match_with_final_score(self):
        nba = {'gameId': '0022600001', 'gameStatus': 3,
               'gameDateTimeUTC': '2026-11-09T01:00:00Z',
               'homeTeam': {'teamTricode': 'GSW', 'score': 110},
               'awayTeam': {'teamTricode': 'WAS', 'score': 109}}
        schedule = {'leagueSchedule': {'gameDates': [{'games': [nba]}]}}
        espn = {'game_id': 'espn-1', 'tipoff_utc': '2026-11-09T01:00:00+00:00',
                'home_team': 'GS', 'away_team': 'WSH', 'home_points': 110, 'away_points': 109}
        args = (date(2026, 11, 8), {'GS'}, '00226')
        self.assertEqual(bind_history(schedule, [espn], *args), ({'espn-1': '0022600001'}, {}))
        wrong_score = dict(espn, away_points=108)
        self.assertEqual(bind_history(schedule, [wrong_score], *args),
                         ({}, {'espn-1': 'no_exact_match'}))
        duplicate = dict(nba, gameId='0022600002')
        schedule['leagueSchedule']['gameDates'][0]['games'].append(duplicate)
        self.assertEqual(bind_history(schedule, [espn], *args),
                         ({}, {'espn-1': 'ambiguous_or_repeated'}))

    def test_team_ml_requires_pregame_observations_and_supported_ratings(self):
        from livedata_team_metrics import research_projection
        from reproducible_slate import digest

        snapshot = {'created_at_utc': '2026-11-09T10:00:00Z', 'predictions': [
            {'game_id': 'future', 'tipoff_utc': '2026-11-09T20:00:00Z',
             'home_team': 'GS', 'away_team': 'WSH', 'hybrid_p_home': .55}]}
        snapshot['content_sha256'] = digest(snapshot)
        games = [
            {'game_id': str(day), 'tipoff_utc': f'2026-11-0{day}T01:00:00Z',
             'observed_at_utc': '2026-11-09T11:00:00Z',
             'regulation_and_overtime_minutes': 48,
             'teams': [{'team': 'GSW', 'points': 112, 'possessions_estimated': 100},
                       {'team': 'WAS', 'points': 107, 'possessions_estimated': 100}]}
            for day in (1, 2, 3)]
        source = {'fallback': {'games': games}}
        result = research_projection(snapshot, source, '2026-11-09T12:00:00Z')['games'][0]
        self.assertEqual(result['status'], 'research_team_ml')
        self.assertAlmostEqual(result['home_ml'] + result['away_ml'], 1.0)
        self.assertIsNone(result['home_plus20'])
        games[2]['observed_at_utc'] = '2026-11-09T12:30:00Z'
        result = research_projection(snapshot, source, '2026-11-09T12:00:00Z')['games'][0]
        self.assertEqual(result['status'], 'PASS_insufficient_opponent_sample')
        result = research_projection(snapshot, source, '2026-11-09T20:00:00Z')['games'][0]
        self.assertEqual(result['status'], 'PASS_already_started')
