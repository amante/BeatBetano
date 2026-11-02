from datetime import datetime
import copy
import json
from pathlib import Path
import tempfile
import unittest
from nhl.tests.test_goalie_prospective_evaluation import fixture
from nhl.goalie_ml_inference import infer, package, validate_artifact
from nhl.goalie_prospective_evaluation import digest
from nhl.pulso_goalie_model_269 import train

AT=datetime.fromisoformat('2026-11-02T20:02:00+00:00')


def fitted_artifact():
    # Fitted test data only, never shipped as real NHL parameters.
    xs=[[.2*(i%3-1),.025*(i%2*2-1)] for i in range(100)]
    ys=[i%2 for i in range(100)]
    m=train(xs,ys,steps=300)
    b=train([[x[0]] for x in xs],ys,steps=300)
    evaluation=dict(kind='nhl_prospective_goalie_evaluation_v1',status='research_evaluated_not_promoted',protocol='goalie-v1-fixed-dates',fit_through='2026-01-01',validation_through='2026-02-01',test_through='2026-03-01',fit_n=400,validation_n=50,test_n=100,input_rows_sha256='a'*64,models={'recalibration_only':{'model':b},'recalibration_plus_goalie':{'model':m}},metrics={name:{'n':100,'brier':.25,'log_loss':.69} for name in ('baseline','recalibration_only','recalibration_plus_goalie')})
    return package(evaluation,'2026-04-01T00:00:00Z')


def slate():
    return dict(kind='nhl_research_daily_presentation_275',date='2026-11-02',run_id='123',official=False,odds_used=False,games=[dict(game_id='2026020232',home='BOS',away='VGK',start_utc='2026-11-03T00:00:00Z',ml={'home':.55,'away':.45})])


class GoalieInferenceTests(unittest.TestCase):
    def test_missing_artifact_is_not_zero_adjustment(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture(Path(temp));r=infer(temp,'123',slate(),at=AT)['games'][0]
            self.assertEqual(r['status'],'goalie_model_not_executed')
            self.assertIsNone(r['candidate_p_home']);self.assertIsNone(r['delta_vs_baseline_pp'])
            self.assertIn('missing_fitted_model',r['reasons'])

    def test_learned_model_is_sensitive_to_goalie_rate(self):
        model=fitted_artifact()
        with tempfile.TemporaryDirectory() as temp:
            output,_=fixture(Path(temp))
            first=infer(temp,'123',slate(),model,AT)['games'][0]
            data=json.loads(output.read_text())
            for t,rate in [('BOS',.95),('VGK',.85)]:
                metric=data['games'][0]['teams'][t]['goalie_prior_statistics']['season_to_date']
                metric.update(save_pct=rate,saves=int(rate*100))
            data['content_sha256']=digest({k:v for k,v in data.items() if k!='content_sha256'})
            output.write_text(json.dumps(data))
            second=infer(temp,'123',slate(),model,AT)['games'][0]
            self.assertEqual(first['status'],'experimental_goalie_ml_executed')
            self.assertGreater(second['candidate_p_home'],first['candidate_p_home'])
            self.assertEqual(second['baseline_p_home'],first['baseline_p_home'])
            self.assertAlmostEqual(second['candidate_p_home']+second['candidate_p_away'],1.)
            self.assertAlmostEqual(second['delta_vs_baseline_pp'],100*(second['candidate_p_home']-.55))
            self.assertEqual(second['recalibration_p_home'],first['recalibration_p_home'])

    def test_wrong_contract_bad_dimensions_and_changed_hash_rejected(self):
        model=fitted_artifact()
        for mutate in ('contract','parameters','hash'):
            broken=copy.deepcopy(model)
            if mutate=='contract':broken['contract']='old-269'
            if mutate=='parameters':
                broken['candidate']['mean']=[]
                broken['artifact_sha256']=digest({k:v for k,v in broken.items() if k!='artifact_sha256'})
            if mutate=='hash':broken['candidate']['coef'][0]+=1
            with self.assertRaises(ValueError):validate_artifact(broken,AT)
        with self.assertRaises(ValueError):package({'kind':'nhl_goalie_ml_research_backtest_269'},AT.isoformat())

    def test_late_model_wrong_emission_and_started_fixture_not_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture(Path(temp));model=fitted_artifact()
            late=copy.deepcopy(model);late['available_at_utc']='2026-11-02T20:01:30Z';late['artifact_sha256']=digest({k:v for k,v in late.items() if k!='artifact_sha256'})
            r=infer(temp,'123',slate(),late,AT)['games'][0]
            self.assertIn('model_unavailable_at_baseline_issuance',r['reasons'])
            r=infer(temp,'123',slate(),model,datetime.fromisoformat('2026-11-03T01:00:00+00:00'))['games'][0]
            self.assertIn('fixture_already_started',r['reasons'])
            wrong=slate();wrong['run_id']='124'
            with self.assertRaises(ValueError):infer(temp,'123',wrong,model,AT)
            wrong=slate();wrong['games'][0]['ml']['home']=.6
            with self.assertRaises(ValueError):infer(temp,'123',wrong,model,AT)

class FailedCandidateAssessment(unittest.TestCase):
    def test_real_evaluation_failure_is_explicit_and_not_a_zero_effect(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            path=root/'nhl/models/goalie-ml-assessment.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps(dict(kind='nhl_goalie_ml_assessment_v1',decision='not_approved_no_incremental_gain',metrics={'baseline':{'brier':.24,'log_loss':.68},'recalibration_only':{'brier':.23,'log_loss':.67},'recalibration_plus_goalie':{'brier':.25,'log_loss':.69}})))
            r=infer(temp,'123',slate(),at=AT)
            self.assertIn('model_failed_incremental_evaluation',r['games'][0]['reasons'])
            self.assertIsNone(r['games'][0]['candidate_p_home'])
            self.assertIsNone(r['games'][0]['delta_vs_baseline_pp'])
