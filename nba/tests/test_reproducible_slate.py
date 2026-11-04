import copy
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reproducible_slate import adjusted_ratings, build, digest


def observation(gid,home,away,hp,ap,poss=100):
    return {'game':{'game_id':str(gid),'home_team':home,'away_team':away,
                    'tipoff_utc':'2026-10-25T00:00:00Z','home_points':hp,'away_points':ap},
            'observed_at_utc':'2026-11-04T20:00:00Z',
            'team_statistics':{home:{'points':hp,'possessions_estimated':poss},
                               away:{'points':ap,'possessions_estimated':poss}},'players':[]}


def snapshot():
    s={'created_at_utc':'2026-11-04T21:00:00Z','predictions':[
        {'game_id':'future','home_team':'A','away_team':'B','tipoff_utc':'2026-11-05T00:00:00Z',
         'elo_p_home':.6,'challenger_p_home':.65}]}
    s['content_sha256']=digest(s)
    return s


class ReproducibleSlateTests(unittest.TestCase):
    def test_known_balanced_rates_and_both_sides(self):
        box={'games':[observation(i,'A','B',120,100) for i in range(3)]}
        rates=adjusted_ratings(box,'2026-11-04T21:00:00Z')
        # Opponent baseline has exactly the same scores: residuals are zero.
        self.assertAlmostEqual(rates['A']['league_rating'],110)
        self.assertAlmostEqual(rates['A']['opponent_adjusted_ortg'],110)
        report=build(snapshot(),box)
        g=report['games'][0]
        self.assertEqual(set(g['teams']),{'A','B'})
        for t in g['teams'].values():
            self.assertEqual(t['research_projected_possessions'],100)
            self.assertAlmostEqual(t['research_matchup_ppp'],1.1)
            self.assertIsNone(t['reach_plus20_probability'])
            self.assertIsNone(t['availability_adjusted_ortg'])
        for m in g['executed_baselines'].values():
            self.assertAlmostEqual(m['home_ml']+m['away_ml'],1)

    def test_unequal_schedule_hand_calculated_residuals(self):
        rows=[observation(1,'A','B',120,100),observation(2,'A','B',110,100),
              observation(3,'A','C',130,90),observation(4,'B','C',105,95),
              observation(5,'B','C',100,100),observation(6,'A','C',125,100)]
        a=adjusted_ratings({'games':rows},'2026-11-04T21:00:00Z')['A']
        self.assertAlmostEqual(a['raw_ortg'],121.25)
        self.assertAlmostEqual(a['league_rating'],106.25)
        self.assertAlmostEqual(a['opponent_adjusted_ortg'],120.4166666667)
        self.assertAlmostEqual(a['opponent_adjusted_drtg'],104.5833333333)

    def test_late_optional_evidence_is_rejected(self):
        s=snapshot()
        roster={'snapshot_sha256':s['content_sha256'], 'games':{'future':{'teams':{
            'A':{'observed_at_utc':'2026-11-04T22:00:00Z','players':[]}}}}}
        with self.assertRaises(ValueError):build(s,{'games':[]},roster=roster)

    def test_excludes_late_observation_even_if_game_is_old(self):
        row=observation(1,'A','B',120,100)
        row['observed_at_utc']='2026-11-04T22:00:00Z'
        self.assertEqual(adjusted_ratings({'games':[row]},'2026-11-04T21:00:00Z'),{})

    def test_rejects_duplicate_nan_and_mismatched_points(self):
        row=observation(1,'A','B',120,100)
        with self.assertRaises(ValueError):adjusted_ratings({'games':[row,row]},'2026-11-04T21:00:00Z')
        for val in (float('nan'),0,True,99):
            bad=copy.deepcopy(row);bad['team_statistics']['A']['points']=val
            with self.assertRaises(ValueError):adjusted_ratings({'games':[bad]},'2026-11-04T21:00:00Z')

    def test_hash_tamper_and_started_fixture(self):
        s=snapshot();s['predictions'][0]['elo_p_home']=.8
        with self.assertRaises(ValueError):build(s,{'games':[]})
        s=snapshot();s['created_at_utc']='2026-11-05T00:00:00Z'
        s['content_sha256']=digest({k:v for k,v in s.items() if k!='content_sha256'})
        with self.assertRaises(ValueError):build(s,{'games':[]})

    def test_missing_data_is_null_and_never_fabricates_rotation(self):
        r=build(snapshot(),{'games':[]})['games'][0]
        for t in r['teams'].values():
            self.assertEqual(t['players'],[])
            self.assertIsNone(t['research_matchup_ppp'])
            self.assertIsNone(t['final_ml_probability'])

    def test_minutes_require_every_member_and_240(self):
        s=snapshot();link={'snapshot_sha256':s['content_sha256'],'games':{'future':{'teams':{'A':{
            'players':[{'player_id':str(i),'player':str(i)} for i in range(6)]}}}}}
        mins={'snapshot_sha256':s['content_sha256'],'games':{'future':{'teams':{'A':{'allocations':{str(i):48 for i in range(5)}}}}}}
        with self.assertRaises(ValueError):build(s,{'games':[]},roster=link,minutes=mins)

    def test_excludes_knicks_and_mismatched_evidence(self):
        s=snapshot();s['predictions'][0]['home_team']='NY'
        s['content_sha256']=digest({k:v for k,v in s.items() if k!='content_sha256'})
        with self.assertRaises(ValueError):build(s,{'games':[]})
        with self.assertRaises(ValueError):build(snapshot(),{'games':[]},roster={'snapshot_sha256':'other'})

if __name__=='__main__':unittest.main()
