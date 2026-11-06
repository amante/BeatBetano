"""Integrity and conservative source-to-feature boundaries."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reproducible_slate import digest
from source_readiness import audit
from verifiable_capture import score_path, sports_summary
from official_injury_table import extract


class ReadinessTests(unittest.TestCase):
    def capture(self, root):
        cohort = {'created_at_utc':'2026-11-06T12:00:00Z', 'predictions':[
            {'game_id':'1','tipoff_utc':'2026-11-07T00:00:00Z','home_team':'H','away_team':'A'}]}
        cohort['content_sha256'] = digest(cohort)
        rosters = {'snapshot_sha256':cohort['content_sha256'], 'games':{'1':{'teams':{
            t:{'roster_complete':True,'players':[{'player_id':t,'player':t}],
               'observed_at_utc':'2026-11-06T13:00:00Z'} for t in ('H','A')}}}}
        docs = {'fixture_cohort.json':cohort, 'rosters.json':rosters,
                'lineups.json':{'snapshot_sha256':cohort['content_sha256'], 'games':{}},
                'historical_boxscores.json':{'games':[]}}
        for name, data in docs.items():
            (root/name).write_text(json.dumps(data))
        self.manifest(root)

    def manifest(self, root):
        (root/'manifest.json').write_text(json.dumps({'files':{
            p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.iterdir() if p.name != 'manifest.json'}}))

    def test_missing_sources_stay_unknown_both_teams(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.capture(root)
            report = audit(root)
            self.assertEqual(len(report['teams']),2)
            self.assertEqual(report['model_ready_games'],0)
            self.assertTrue(all(t['unknown_status_players']==1 for t in report['teams']))
            self.assertFalse(report['production_approved'])

    def test_tamper_and_unmanifested_sources_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.capture(root)
            (root/'rosters.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'digest mismatch'):audit(root)
            self.capture(root)
            data=json.loads((root/'manifest.json').read_text())
            data['files'].pop('lineups.json')
            (root/'manifest.json').write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'required inputs'):audit(root)

    def test_cross_cohort_and_duplicate_player_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.capture(root)
            p=root/'rosters.json'; data=json.loads(p.read_text())
            data['snapshot_sha256']='bad'; p.write_text(json.dumps(data)); self.manifest(root)
            with self.assertRaisesRegex(ValueError,'cohort mismatch'):audit(root)
            self.capture(root); data=json.loads(p.read_text())
            players=data['games']['1']['teams']['H']['players']; players.append(players[0])
            p.write_text(json.dumps(data)); self.manifest(root)
            with self.assertRaisesRegex(ValueError,'Duplicate roster'):audit(root)

    def test_manifest_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.capture(root)
            p=root/'manifest.json'; data=json.loads(p.read_text()); data['files']['../escape']='a'*64
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'Unsafe'):audit(root)

    def test_post_tip_roster_is_not_pregame(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.capture(root)
            p=root/'rosters.json'; data=json.loads(p.read_text())
            data['games']['1']['teams']['H']['observed_at_utc']='2026-11-07T01:00:00Z'
            p.write_text(json.dumps(data)); self.manifest(root)
            row=audit(root)['teams'][0]
            self.assertFalse(row['roster_observed_pregame'])
            self.assertIn('complete_pregame_roster',row['blocking_requirements'])


class CaptureTests(unittest.TestCase):
    def test_document_context_survives_page_break_only_with_matching_headers(self):
        header='Injury Report: 11/06/26 07:45 AM\n'
        pages=[header+'Game Date Player Name\n11/06/2026 BOS@CHA Boston Celtics Brown, Jaylen Out',
               header+'White, Derrick Questionable\nCharlotte Hornets Ball, LaMelo Out']
        rows=extract(pages,continuous_table=True)
        self.assertEqual([r['game_date'] for r in rows],['11/06/2026']*3)
        self.assertEqual([r['team'] for r in rows],['BOS','BOS','CHA'])
        self.assertEqual(len(extract(pages)),2)
        pages[1]=pages[1].replace('07:45','08:00')
        with self.assertRaises(ValueError):extract(pages,continuous_table=True)

    def test_score_path_checks_each_action_and_accepts_decimal_clock(self):
        plays=[]
        for period in range(1,5):
            plays.append({'id':str(period),'clock':{'displayValue':'0.0'},
                'period':{'number':period},'homeScore':0,'awayScore':0})
        plays.append({'id':'5','clock':{'displayValue':'0.0'},'period':{'number':4},
            'homeScore':2,'awayScore':0,'scoreValue':2,'scoringPlay':True,
            'text':'End of Game'})
        g={'home_points':2,'away_points':0}
        self.assertEqual(score_path({'plays':plays},g)['home_max_lead'],2)
        plays[-1]['homeScore']=5
        with self.assertRaises(ValueError):score_path({'plays':plays},g)


class IdentityResolutionTests(unittest.TestCase):
    def test_punctuation_only_matching_preserves_suffixes_and_ambiguity(self):
        from verifiable_capture import resolve_official
        fixture = {'game_id':'1','home_team':'BOS','away_team':'CLE','tipoff_utc':'2026-11-07T00:00:00Z'}
        players = [{'player_id':'1','player':'Ernest Udeh Jr.'},
                   {'player_id':'2','player':'Terrence Shannon Jr.'}]
        roster = {'games':{'1':{'teams':{'CLE':{'players':players}}}}}
        def claim(name):
            return {'team':'CLE','game_date':'11/06/2026','player':name,'status':'Out','page':1,'line':1}
        def resolve(rows):
            return resolve_official(rows,roster,[fixture],'2026-11-06T12:00:00Z','2026-11-06T13:00:00Z')
        report=resolve([claim('Ernest Udeh, Jr.'),claim('Terrence Shannon Jr')])
        self.assertEqual(len(report['teams'][1]['official_claims']),2)
        self.assertFalse(report['unmatched_claims'])
        self.assertEqual(len(resolve([claim('Ernest Udeh Sr.')])['unmatched_claims']),1)
        players.append({'player_id':'3','player':'Ernest Udeh, Jr'})
        self.assertEqual(len(resolve([claim('Ernest Udeh Jr.')])['unmatched_claims']),1)
        self.assertFalse(report['teams'][1]['complete_active_roster_verified'])

    def test_total_turnovers_include_team_turnovers_in_possession_estimate(self):
        from possession_intelligence import extract as extract_stats
        fixture={'game_id':'1','home_team':'H','away_team':'A'}
        stats=[{'name':k,'displayValue':v} for k,v in
               [('fieldGoalsAttempted','80'),('freeThrowsAttempted','20'),
                ('offensiveRebounds','10'),('turnovers','12'),('totalTurnovers','15'),('points','100')]]
        payload={'header':{'competitions':[{'id':'1','status':{'type':{'completed':True}}}]},
                 'boxscore':{'teams':[{'team':{'abbreviation':t},'statistics':stats} for t in ('H','A')]}}
        result=extract_stats(payload,fixture)
        self.assertAlmostEqual(result['H']['possessions_estimated'],93.8)


if __name__ == '__main__':
    unittest.main()
