import copy
import json
import unittest
from nhl.special_teams_capture import collect,parse_counts,urls
from nhl.sporting_packages import build
from nhl.pulso_sporting_bridge_226 import bridge
from nhl.pulso_quantitative_signals_227 import compute
from nhl.tests import test_sporting_connections as fixtures


def stats():
    pp={'total':2,'data':[dict(seasonId=20262027,teamFullName=name,gamesPlayed=10,powerPlayGoalsFor=4,ppOpportunities=20) for name in ('Boston Bruins','Vegas Golden Knights')]}
    pk={'total':2,'data':[dict(seasonId=20262027,teamFullName=name,gamesPlayed=10,ppGoalsAgainst=3,timesShorthanded=15) for name in ('Boston Bruins','Vegas Golden Knights')]}
    return pp,pk


class SpecialTeamsCapture(unittest.TestCase):
    def test_real_counts_enter_existing_quantitative_signal(self):
        report,rosters,crosswalk,history=fixtures.SportingConnections().data();report['official_predictions']=0
        pp,pk=stats()
        def get(url):
            obj={'currentDate':'2026-11-01','games':[{'gameState':'OFF'}]} if '/score/' in url else pp if '/powerplay?' in url else pk
            return json.dumps(obj).encode(),'2026-11-02T19:35:00Z'
        st,archive=collect(report,get)
        self.assertEqual(st['teams']['BOS']['powerplay_goals'],4)
        self.assertEqual(len(archive),3)
        packages,_=build(report,crosswalk,history,rosters,'2026-11-02T19:45:00Z',st)
        q=compute(bridge(report,crosswalk,{'rosters':rosters},'2026-11-02T19:45:00Z'),packages)
        signal=q['games']['2026020232']['teams']['BOS']['signals']['special_teams']
        self.assertEqual(signal['pp']['observed'],.2)
        self.assertEqual(signal['opponent_pp_allowed']['observed'],.2)
        self.assertFalse(st['probabilities_modified'])

    def test_unfinished_cutoff_day_blocks_all_stats_requests(self):
        report,*_=fixtures.SportingConnections().data();report['official_predictions']=0;calls=[]
        def get(url):
            calls.append(url)
            return json.dumps({'currentDate':'2026-11-01','games':[{'gameState':'LIVE'}]}).encode(),'2026-11-02T19:35:00Z'
        with self.assertRaises(ValueError):collect(report,get)
        self.assertEqual(len(calls),1)

    def test_wrong_season_incomplete_duplicate_and_bad_counts_rejected(self):
        for mutation in ('season','incomplete','duplicate','counts'):
            pp,pk=stats()
            if mutation=='season':pp['data'][0]['seasonId']=20252026
            if mutation=='incomplete':pp['total']=32
            if mutation=='duplicate':pp['data'][1]=copy.deepcopy(pp['data'][0])
            if mutation=='counts':pp['data'][0]['powerPlayGoalsFor']=21
            with self.assertRaises(ValueError):parse_counts(pp,pk,'20262027')

    def test_dated_url_and_zero_opportunities_preserve_missing_rate(self):
        self.assertIn('gameDate',urls('2026-11-01','20262027')['pp'])
        pp,pk=stats();pp['data'][0].update(powerPlayGoalsFor=0,ppOpportunities=0)
        rows,_=parse_counts(pp,pk,'20262027')
        self.assertEqual(rows['BOS']['powerplay_opportunities'],0)
