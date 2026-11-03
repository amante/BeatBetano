import unittest
from nhl.skater_history import summarize

class HistoryTests(unittest.TestCase):
    def row(self,**changes):
        return dict(dict(gameId=1,gameDate='2026-11-01',goals=1,shots=3,toi='18:32'),**changes)
    def test_counts_and_cutoff(self):
        x=summarize(123,{'gameLog':[self.row(),self.row(gameId=2,gameDate='2026-11-02')]},'2026-11-02')
        self.assertEqual((x['skater_games'],x['toi_seconds'],x['skater_shots']),(1,1112,3))
        self.assertFalse(x['applied_to_probability'])
    def test_missing_or_invalid_is_not_zero(self):
        for changes in ({'toi':''},{'toi':'18:60'},{'shots':None},{'goals':4}):
            with self.assertRaises(ValueError):summarize(123,{'gameLog':[self.row(**changes)]},'2026-11-02')
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):summarize(123,{'gameLog':[self.row(),self.row()]},'2026-11-02')
    def test_capture_preserves_source_and_blocks_poststart(self):
        from nhl.skater_history import collect
        report=dict(data_kind='source_readiness_only',official_predictions=0,generated_at_utc='2026-11-02T18:00:00Z',games=[dict(home='BOS',away='MTL',start_utc='2026-11-02T23:00:00Z')])
        rosters=dict(rosters=[dict(team='BOS',as_of='2026-11-02T17:59:00Z',source_url='https://api-web.nhle.com/v1/roster/BOS/current',players=[dict(player_id=123,position_group='forward')])])
        def fetch(pid,season):return {'gameLog':[self.row()]},dict(url=f'https://api-web.nhle.com/v1/player/{pid}/game-log/{season}/2',retrieved_at='2026-11-02T18:01:00Z',sha256='test')
        result,raw=collect(report,rosters,fetch)
        self.assertEqual(result['players']['123']['toi_seconds'],1112)
        self.assertEqual(result['missing_roster_teams'],['MTL'])
        self.assertIn('123',raw)
        def late(pid,season):
            payload,meta=fetch(pid,season);meta['retrieved_at']='2026-11-02T23:00:00Z';return payload,meta
        result,_=collect(report,rosters,late)
        self.assertFalse(result['players']);self.assertIn('123',result['errors'])
    def test_roster_cannot_be_retrodated(self):
        from nhl.skater_history import collect
        report=dict(data_kind='source_readiness_only',official_predictions=0,generated_at_utc='2026-11-02T18:00:00Z',games=[dict(home='BOS',away='MTL',start_utc='2026-11-02T23:00:00Z')])
        with self.assertRaises(ValueError):collect(report,dict(rosters=[dict(team='BOS',as_of='2026-11-02T19:00:00Z',source_url='https://api-web.nhle.com/v1/roster/BOS/current',players=[])]))
    def test_previous_participant_missing_from_current_roster_is_captured(self):
        from nhl.skater_history import collect
        report=dict(data_kind='source_readiness_only',official_predictions=0,generated_at_utc='2026-11-02T18:00:00Z',games=[dict(game_id='1',home='BOS',away='MTL',start_utc='2026-11-02T23:00:00Z')])
        reference=dict(kind='nhl_prior_lineup_reference_v1',games=[dict(game_id='1',teams=dict(BOS=dict(players=[dict(player_id=123,role='forward')],source=dict(url='https://api-web.nhle.com/v1/gamecenter/2/boxscore',retrieved_at='2026-11-02T18:01:00Z'))))])
        def fetch(pid,season):return {'gameLog':[self.row()]},dict(url=f'https://api-web.nhle.com/v1/player/{pid}/game-log/{season}/2',retrieved_at='2026-11-02T18:02:00Z')
        x,_=collect(report,dict(rosters=[]),fetch,reference)
        self.assertIn('123',x['players'])
        reference['games'][0]['teams']['CAR']=reference['games'][0]['teams'].pop('BOS')
        with self.assertRaises(ValueError):collect(report,dict(rosters=[]),fetch,reference)
