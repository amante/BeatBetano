import copy
import unittest
from nhl.goalie_historical_candidate import rebuild,evaluate,artifact


def rows():
    labels=[];records=[]
    for i in range(4):
        gid='202402'+str(i+1).zfill(4);day='2024-10-'+str(i+1).zfill(2)
        label=dict(game_id=gid,date=day,home='BOS',away='VGK',ml_winner='home' if i%2 else 'away')
        teams={}
        for side,pid in [('home',10),('away',20)]:
            teams[side]=dict(starter_id=pid,goalies=[dict(player_id=pid,explicit_starter=True,source_row={'saves':18 if side=='home' else 17,'shotsAgainst':20})])
        labels.append(label);records.append(dict(game_id=gid,date=day,home='BOS',away='VGK',verified_starters=True,teams=teams))
    return labels,records


class HistoricalCandidate(unittest.TestCase):
    def test_prior_appearance_counts_exclude_target_game(self):
        labels,records=rows();before,_=rebuild(labels,records,min_shots=10,warmup=0)
        self.assertAlmostEqual(before[0]['goalies']['home']['save_pct'],.9)
        altered=copy.deepcopy(records);altered[1]['teams']['home']['goalies'][0]['source_row']['saves']=1
        after,_=rebuild(labels,altered,min_shots=10,warmup=0)
        self.assertEqual(before[0],after[0]);self.assertNotEqual(before[1]['goalie_sv_difference'],after[1]['goalie_sv_difference'])

    def test_relief_appearances_enter_the_next_game_prior(self):
        labels,records=rows()
        records[0]['teams']['home']['goalies'].append(dict(player_id=11,explicit_starter=False,source_row={'saves':8,'shotsAgainst':10}))
        records[1]['teams']['home']['starter_id']=11
        records[1]['teams']['home']['goalies']=[dict(player_id=11,explicit_starter=True,source_row={'saves':19,'shotsAgainst':20})]
        built,_=rebuild(labels,records,min_shots=10,warmup=0)
        self.assertEqual(built[0]['goalies']['home']['player_id'],11)
        self.assertAlmostEqual(built[0]['goalies']['home']['save_pct'],.8)

    def test_season_boundary_resets_goalie_prior(self):
        labels,records=rows()
        labels[2].update(game_id='2025020001',date='2025-10-01');records[2].update(game_id='2025020001',date='2025-10-01')
        labels[3].update(game_id='2025020002',date='2025-10-02');records[3].update(game_id='2025020002',date='2025-10-02')
        records[2]['teams']['home']['goalies'][0]['source_row']['saves']=10
        built,_=rebuild(labels,records,min_shots=10,warmup=0)
        self.assertEqual(len(built),2)
        self.assertAlmostEqual(built[-1]['goalies']['home']['save_pct'],.5)
        self.assertEqual(built[-1]['goalies']['home']['shots'],20)

    def test_missing_cache_invalid_dates_and_insufficient_fit_rejected(self):
        labels,records=rows()
        with self.assertRaises(ValueError):rebuild(labels,records[:-1])
        with self.assertRaises(ValueError):evaluate([],fit_through='2026-05-01',validation_through='2026-01-01')
        with self.assertRaises(ValueError):evaluate([])
