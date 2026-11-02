from datetime import datetime
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from nhl.tests.test_player_evidence import inputs, NOW
from nhl.match_context import freeze_player_evidence
from nhl.goalie_prospective_evaluation import cohort, evaluate
from nhl.pulso_collective_audit_208 import freeze_prediction
from nhl.pulso_outcome_forecast_218 import VERSION


def fixture(root,run='123',issued='2026-11-02T20:01:00Z'):
    data=inputs();source=root/'capture';source.mkdir(exist_ok=True)
    payloads={'report.json':data[0],'official_roster_candidates.json':{'rosters':data[1]},'goalie_identity_crosswalk.json':data[2],'goalie_history_251.json':data[3],'goalie_observations.json':{},'espn_raw.json':{}}
    for name,payload in payloads.items():(source/name).write_text(json.dumps(payload))
    (source/'editorial_lineup_raw.html').write_bytes(data[4])
    output=root/'nhl/learning/pregame'/('run-'+run+'.json')
    with patch('nhl.match_context.datetime',wraps=datetime) as clock:
        clock.now.return_value=datetime.fromisoformat(NOW)
        freeze_player_evidence(source,run,output)
    f=root/'frontend/data/nhl-forecasts'/('run-'+run)/'2026020232-ml.json';f.parent.mkdir(parents=True)
    record=dict(game_id='2026020232',home='BOS',away='VGK',start_utc='2026-11-03T00:00:00Z',prediction_as_of_utc=issued,source_asof_utc=issued,source_url='https://example.org/history',model_version=VERSION,market='ml',probabilities={'home':.55,'away':.45},odds_used_in_model=False,point_in_time_sources_verified=True)
    f.write_text(json.dumps(freeze_prediction(record)))
    return output,f


def result(root,home='BOS'):
    p=root/'frontend/data/nhl-postmortems/2026-11-02.json';p.parent.mkdir(parents=True,exist_ok=True)
    core=dict(kind='nhl_daily_postmortem',date='2026-11-02',games=[dict(game_id='2026020232',home=home,away='VGK',start_utc='2026-11-03T00:00:00Z',state='OFF',outcomes={'ml_winner':'home'})])
    sha=hashlib.sha256(json.dumps(core,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    p.write_text(json.dumps(dict(core,revision_sha256=sha,generated_at_utc='2026-11-03T05:00:00Z')))


class ProspectiveCohortTests(unittest.TestCase):
    def test_pending_then_official_final_and_no_duplicate_issuances(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root);fixture(root,'124','2026-11-02T20:02:00Z')
            r=cohort(root);self.assertEqual(len(r['pending']),1);self.assertEqual(r['duplicate_issuances_discarded'],1)
            result(root);r=cohort(root)
            self.assertEqual(len(r['rows']),1);self.assertEqual(r['rows'][0]['run_id'],'123')
            self.assertEqual(r['rows'][0]['y_home_win'],1);self.assertFalse(r['probabilities_modified'])

    def test_tampered_sources_or_forecast_quarantine_whole_run(self):
        for target in ('source','forecast'):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);output,f=fixture(root)
                if target=='source':output.with_suffix('.sources.json.gz').write_bytes(b'corrupted gzip')
                else:
                    d=json.loads(f.read_text());d['record']['probabilities']={'home':.7,'away':.3};f.write_text(json.dumps(d))
                r=cohort(root);self.assertEqual(r['pending'],[]);self.assertEqual(r['excluded'][0]['reason'],'invalid_evidence')

    def test_evidence_cannot_attach_to_earlier_forecast(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root,issued='2026-11-02T19:00:00Z')
            r=cohort(root);self.assertEqual(r['pending'],[]);self.assertEqual(r['excluded'][0]['reason'],'invalid_evidence')

    def test_missing_same_run_and_mismatched_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);_,f=fixture(root);f.unlink()
            self.assertEqual(cohort(root)['excluded'][0]['reason'],'missing_same_run_baseline')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root);result(root,'TOR')
            with self.assertRaises(ValueError):cohort(root)

    def test_protocol_requires_dates_and_sufficient_separated_data(self):
        data=dict(kind='nhl_prospective_goalie_cohort_v1',rows=[])
        self.assertEqual(evaluate(data,'2026-11-02','2026-12-01','2027-01-01')['status'],'insufficient_chronological_evidence')
        with self.assertRaises(ValueError):evaluate(data,'2027-01-01','2026-12-01','2026-11-02')

    def test_three_arm_evaluation_ignores_test_labels_during_fitting(self):
        rows=[]
        for group,(days,n) in enumerate([(('2026-01-01','2026-01-02'),400),(('2026-02-01','2026-02-02'),50),(('2026-03-01','2026-03-02'),100)]):
            for i in range(n):
                day=days[i%2]
                rows.append(dict(game_id=str(group*1000+i),date=day,y_home_win=i%2,baseline_p_home=.45+.1*(i%2),goalie_sv_difference=(-.02 if i%2==0 else .02),prediction_as_of_utc=day+'T18:00:00Z',outcome_available_at_utc=day+'T23:00:00Z'))
        data=dict(kind='nhl_prospective_goalie_cohort_v1',rows=rows)
        calls=[]
        # Fast deterministic learner records the actual labels used by each trial.
        def learner(xs,ys,l2):
            calls.append((copy.deepcopy(xs),list(ys),l2))
            return {'value':.5,'features':len(xs[0])}
        with patch('nhl.goalie_prospective_evaluation.train',side_effect=learner),patch('nhl.goalie_prospective_evaluation.predict',return_value=.5):
            report=evaluate(data,'2026-01-02','2026-02-02','2026-03-02')
            first=copy.deepcopy(calls);calls.clear()
            altered=copy.deepcopy(data)
            for r in altered['rows'][450:]:r['y_home_win']=1-r['y_home_win']
            second=evaluate(altered,'2026-01-02','2026-02-02','2026-03-02')
        self.assertEqual(first,calls);self.assertEqual(report['models'],second['models'])
        self.assertEqual(set(report['metrics']),{'baseline','recalibration_only','recalibration_plus_goalie'})
        self.assertEqual(len(report['test_predictions']),100)
        self.assertFalse(report['automatic_promotion'])
        late=copy.deepcopy(data);late['rows'][0]['outcome_available_at_utc']='2026-03-02T23:00:00Z'
        self.assertEqual(evaluate(late,'2026-01-02','2026-02-02','2026-03-02')['status'],'outcomes_unavailable_at_training_cutoff')
