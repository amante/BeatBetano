import copy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from nhl.match_context import player_evidence, freeze_player_evidence

NOW='2026-11-02T20:00:00+00:00'
START='2026-11-03T00:00:00Z'
SHA='a'*64


def inputs():
    fixture=dict(game_id='2026020232',home='BOS',away='VGK',start_utc=START)
    report=dict(data_kind='source_readiness_only',generated_at_utc='2026-11-02T19:00:00Z',games=[fixture])
    rosters=[]; observations=[]; sides={}
    article='<script type="application/ld+json">'+json.dumps({'@type':'NewsArticle','dateModified':'2026-11-02T18:30:00Z'})+'</script>'
    for index,(team,label) in enumerate([('BOS','Bruins'),('VGK','Golden Knights')]):
        players=[]
        for i in range(18): players.append(dict(player_id=1000+index*100+i,full_name=team+' Player '+str(i),position_group='forward' if i<12 else 'defense'))
        players.append(dict(player_id=2000+index,full_name=team+' Goalie',position_group='goalie'))
        rosters.append(dict(team=team,as_of='2026-11-02T18:00:00Z',source_url='https://api-web.nhle.com/v1/roster/'+team+'/current',source_sha256=SHA,players=players))
        article+='<h3>'+label+' projected lineup</h3>'
        for i in range(0,12,3): article+='<p>'+' -- '.join(p['full_name'] for p in players[i:i+3])+'</p>'
        for i in range(12,18,2): article+='<p>'+' -- '.join(p['full_name'] for p in players[i:i+2])+'</p>'
        article+='<p>'+team+' Goalie</p><p>Scratched: None</p><p>Injured: None</p><p>Status report</p>'
        observations.append(dict(nhl_game_id=fixture['game_id'],team=team,usable_pregame_identity=True,matchup_verified=True,validation_errors=[],event_start=START,source_captured_at='2026-11-02T18:45:00Z',nhl_player_id=2000+index,goalie_status='confirmed',source_url='https://site.api.espn.com/scoreboard'))
        metric=dict(games=5,shots_against=100,saves=90,save_pct=.9)
        sides[team]=dict(nhl_player_id=2000+index,status='observed',source=dict(url='https://api-web.nhle.com/v1/player/'+str(2000+index)+'/game-log/20262027/2',sha256=SHA,retrieved_at='2026-11-02T19:30:00Z'),metrics=dict(cutoff_exclusive='2026-11-02',season_to_date=metric,last_5_games=metric))
    return [report,rosters,dict(retrieved_at='2026-11-02T18:45:00Z',observations=observations),dict(games=[dict(fixture,teams=sides)]),article.encode()]


class PlayerEvidenceTests(unittest.TestCase):
    def test_identity_and_numeric_history_connected_but_no_fitted_effect(self):
        result=player_evidence(*inputs(),NOW)
        t=result['games'][0]['teams']['BOS']
        self.assertTrue(t['projected_skaters_identity_complete'])
        self.assertEqual(t['goalie_player_id'],2000)
        self.assertEqual(t['goalie_provider_status'],'confirmed')
        self.assertFalse(t['independent_starter_confirmation'])
        self.assertEqual(t['goalie_prior_statistics']['last_5_games']['save_pct'],.9)
        self.assertEqual(t['projected']['injuries'],[])
        self.assertFalse(t['model_eligible'])
        self.assertIsNone(result['games'][0]['applied_probability_delta'])

    def test_missing_injured_identity_does_not_mean_no_injuries(self):
        data=inputs();data[-1]=data[-1].replace(b'Injured: None',b'Injured: Unknown Player (knee)')
        t=player_evidence(*data,NOW)['games'][0]['teams']['BOS']
        self.assertIsNone(t['projected']['injuries'][0]['player_id'])
        self.assertIn('injuries_missing_or_unresolved',t['blockers'])

    def test_duplicate_or_conflicting_line_players_reject_completeness(self):
        for replacement in (b'BOS Player 0 -- BOS Player 0 -- BOS Player 2',):
            data=inputs();data[-1]=data[-1].replace(b'BOS Player 0 -- BOS Player 1 -- BOS Player 2',replacement)
            t=player_evidence(*data,NOW)['games'][0]['teams']['BOS']
            self.assertFalse(t['projected_skaters_identity_complete'])
            self.assertTrue(t['duplicate_player_ids'])
        data=inputs();data[-1]=data[-1].replace(b'Injured: None',b'Injured: BOS Player 0 (knee)')
        t=player_evidence(*data,NOW)['games'][0]['teams']['BOS']
        self.assertTrue(t['availability_conflict'])
        self.assertFalse(t['projected_skaters_identity_complete'])

    def test_old_article_late_roster_and_started_fixture(self):
        data=inputs();data[-1]=data[-1].replace(b'2026-11-02T18:30',b'2026-11-01T18:30')
        t=player_evidence(*data,NOW)['games'][0]['teams']['BOS']
        self.assertIsNone(t['projected']['forwards'])
        data=inputs();data[1][0]['as_of']='2026-11-03T01:00:00Z'
        with self.assertRaises(ValueError):player_evidence(*data,NOW)
        result=player_evidence(*inputs(),'2026-11-03T01:00:00Z')
        self.assertEqual(result['games'],[])
        self.assertEqual(result['skipped_started_games'],['2026020232'])

    def test_wrong_fixture_ambiguous_goalie_and_missing_history(self):
        for mutation in ('wrong','duplicate','missing'):
            data=inputs()
            if mutation=='wrong':data[2]['observations'][0]['event_start']='2026-11-03T01:00:00Z'
            elif mutation=='duplicate':data[2]['observations'].append(copy.deepcopy(data[2]['observations'][0]))
            else:data[3]['games']=[]
            t=player_evidence(*data,NOW)['games'][0]['teams']['BOS']
            self.assertIsNone(t['goalie_prior_statistics'])
            if mutation!='missing':self.assertIsNone(t['goalie_player_id'])
        data=inputs();data[3]['games'][0]['away']='TOR'
        with self.assertRaises(ValueError):player_evidence(*data,NOW)

    def test_malformed_statistics_and_unattributed_roster_rejected(self):
        data=inputs();data[3]['games'][0]['teams']['BOS']['metrics']['season_to_date']['save_pct']=float('nan')
        with self.assertRaises(ValueError):player_evidence(*data,NOW)
        data=inputs();data[1][0].pop('source_sha256')
        with self.assertRaises(ValueError):player_evidence(*data,NOW)

    def test_freeze_retains_original_sources_and_is_append_only(self):
        data=inputs()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'run-123.json'
            payloads={'report.json':data[0],'official_roster_candidates.json':{'rosters':data[1]},'goalie_identity_crosswalk.json':data[2],'goalie_history_251.json':data[3],'goalie_observations.json':{},'espn_raw.json':{}}
            for name,payload in payloads.items():(root/name).write_text(json.dumps(payload))
            (root/'editorial_lineup_raw.html').write_bytes(data[4])
            with patch('nhl.match_context.datetime',wraps=datetime) as clock:
                clock.now.return_value=datetime.fromisoformat(NOW)
                result=freeze_player_evidence(root,'123',out)
                before=out.read_bytes()
                with self.assertRaises(FileExistsError):freeze_player_evidence(root,'123',out)
            self.assertEqual(out.read_bytes(),before)
            bundle=json.loads(gzip.decompress(out.with_suffix('.sources.json.gz').read_bytes()))
            for name,text in bundle.items():self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),result['source_files_sha256'][name])
