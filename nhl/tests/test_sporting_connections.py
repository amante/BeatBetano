import copy
import unittest
from nhl.tests.test_player_evidence import inputs
from nhl.pulso_sporting_bridge_226 import bridge
from nhl.sporting_packages import build
from nhl.pulso_quantitative_signals_227 import compute


class SportingConnections(unittest.TestCase):
    def data(self):
        report,rosters,crosswalk,history,_=inputs()
        history.update(kind='nhl_candidate_goalie_history_251',as_of_utc=report['generated_at_utc'])
        return report,rosters,crosswalk,history

    def test_producer_ids_and_real_history_reach_quantitative_signal(self):
        report,rosters,crosswalk,history=self.data()
        cutoff='2026-11-02T19:45:00Z'
        b=bridge(report,crosswalk,{'rosters':rosters},cutoff)
        self.assertEqual(b['games']['2026020232']['teams']['BOS']['provider_goalie_id_observed'],2000)
        packages,excluded=build(report,crosswalk,history,rosters,cutoff)
        self.assertEqual(excluded,[])
        q=compute(b,packages)['games']['2026020232']['teams']['BOS']
        self.assertEqual(q['signals']['goalie']['prior_save_pct'],.9)
        self.assertNotIn('crs',q['signals']);self.assertNotIn('special_teams',q['signals'])
        self.assertFalse(packages['2026020232']['BOS']['goalie']['starter_independently_confirmed'])
        self.assertEqual(packages['2026020232']['BOS']['goalie']['as_of'],'2026-11-02T19:30:00Z')

    def test_no_backdating_and_mismatched_ids_fail_closed(self):
        report,rosters,crosswalk,history=self.data()
        with self.assertRaises(ValueError):build(report,crosswalk,history,rosters,report['generated_at_utc'])
        crosswalk['observations'][0]['game_id']='999'
        with self.assertRaises(ValueError):bridge(report,crosswalk,{'rosters':rosters})

    def test_missing_history_remains_missing_and_poststart_rejected(self):
        report,rosters,crosswalk,history=self.data()
        history['games'][0]['teams'].pop('BOS')
        packages,excluded=build(report,crosswalk,history,rosters,'2026-11-02T19:45:00Z')
        self.assertEqual(packages['2026020232']['BOS'],{})
        self.assertEqual(excluded[0]['team'],'BOS')
        with self.assertRaises(ValueError):build(report,crosswalk,history,rosters,'2026-11-03T01:00:00Z')

    def test_unmatched_goalie_role_is_not_independently_verified(self):
        report,rosters,crosswalk,history=self.data()
        for p in rosters[0]['players']:
            if p['player_id']==2000:p['position_group']='defense'
        with self.assertRaises(ValueError):build(report,crosswalk,history,rosters,'2026-11-02T19:45:00Z')
