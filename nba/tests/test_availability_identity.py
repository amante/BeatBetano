import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sporting_feed import extract
from player_status_intake import reconcile
from lineup_live_collector import parse_rotowire
from test_lineup_live_collector import HTML

T='2026-11-04T21:45:00Z'
S={'content_sha256':'s','predictions':[{'game_id':'1','home_team':'WSH','away_team':'ATL','tipoff_utc':'2026-11-05T00:00:00Z'}]}
R={'snapshot_sha256':'s','games':{'1':{'teams':{'WSH':{'players':[{'player_id':'7','player':'Alex Player'}]},'ATL':{'players':[]}}}}}

def payload():
    return {'injuries':[{'id':'27','displayName':'Washington Wizards','injuries':[
        {'athlete':{'displayName':'Alex Player','team':{'id':'27','abbreviation':'WAS'}},'status':'Out','date':'2026-11-04T20:00:00Z'}]}]}

class IdentityTests(unittest.TestCase):
    def test_current_shape_and_alias_reach_roster(self):
        sporting=extract(payload(),S,T)
        row=sporting['games']['1']['supplementary_injury_observations']['items'][0]
        self.assertEqual(row['team'],'WSH')
        out=reconcile(S,R,sporting)
        self.assertEqual(out['games']['1']['teams']['WSH'][0]['player_id'],'7')
        self.assertFalse(sporting['games']['1']['complete_pregame'])

    def test_conflicting_group_id_rejected(self):
        p=payload();p['injuries'][0]['id']='99'
        s=extract(p,S,T)
        self.assertEqual(s['games']['1']['supplementary_injury_observations']['items'],[])
        self.assertEqual(s['rejected_claims'][0]['reason'],'conflicting_team_ids')

    def test_conflicting_group_abbreviation_rejected(self):
        p=payload();p['injuries'][0]['team']={'abbreviation':'BOS'}
        self.assertEqual(extract(p,S,T)['rejected_claims'][0]['reason'],'conflicting_team_abbreviations')

    def test_id_matches_renamed_player_and_wrong_id_never_falls_back(self):
        p=payload();p['injuries'][0]['injuries'][0]['athlete'].update(id='7',displayName='A. Player')
        out=reconcile(S,R,extract(p,S,T))
        self.assertEqual(out['games']['1']['teams']['WSH'][0]['identity_match'],'provider_id')
        p['injuries'][0]['injuries'][0]['athlete'].update(id='999',displayName='Alex Player')
        self.assertEqual(len(reconcile(S,R,extract(p,S,T))['unmatched_claims']),1)

    def test_future_report_metadata_not_used(self):
        p=payload();p['injuries'][0]['injuries'][0]['date']='2026-11-06T20:00:00Z'
        self.assertEqual(reconcile(S,R,extract(p,S,T))['games']['1']['teams']['WSH'],[])

    def test_missing_identity_cannot_be_assigned_from_display_name(self):
        p=payload();p['injuries'][0]['injuries'][0]['athlete'].pop('team')
        self.assertEqual(extract(p,S,T)['games']['1']['supplementary_injury_observations']['items'],[])

    def test_lineup_alias_preserves_fixture_team_codes(self):
        html=HTML.replace('IND','WAS').replace('MIL','SAS')
        snap={'predictions':[{'game_id':'9','home_team':'SA','away_team':'WSH'}]}
        rows,_=parse_rotowire(html,snap,T)
        self.assertEqual([r['team'] for r in rows],['WSH','SA'])

if __name__=='__main__':unittest.main()
