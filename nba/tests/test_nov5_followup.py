"""Observed boundaries and synthetic sensitivity checks, never fitted outcomes."""
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_postmortem_engine import inputs, build, team, TIP
from postmortem_engine import team_projection
from score_path import lead_events


class November5Tests(unittest.TestCase):
    def test_observed_cases_never_become_predictions(self):
        evidence = json.loads((Path(__file__).resolve().parents[1]/'postmortem_validation/nov5_observed_evidence.json').read_text())
        self.assertEqual(evidence['calibration']['eligible_predictions'],0)
        self.assertIsNone(evidence['model_hits'])
        self.assertIsNone(evidence['dual'])
        for g in evidence['games']:
            for model in ('official_pregame','challenger_pregame'):
                self.assertTrue(all(v is None for v in g[model].values()))
        # Constructed witness paths reconcile reported boundaries only.
        # They do not assert an actual possession order or opponent maximum lead.
        phx = [(0,1)]*30 + [(1,1)]*17 + [(side,1) for _ in range(87) for side in (1,0)]
        gsw = [(0,1)]*20 + [(side,1) for _ in range(100) for side in (1,0)]
        self.assertEqual(lead_events(phx)[:3],(117,104,30))
        self.assertEqual(lead_events(gsw)[:3],(120,100,20))

    def test_fatigue_overtime_and_depth_affect_both_sides(self):
        s,e,b = inputs()
        before = build(s,e,b,simulations=100)['games'][0]['challenger']
        for side in ('H','A'):
            changed = copy.deepcopy(e)
            t = changed['games']['future']['teams'][side]
            t['schedule'] = {'previous_tipoff_utc':'2026-11-05T00:00:00Z',
                             'previous_completed_at_utc':'2026-11-05T03:00:00Z',
                             'previous_overtime_periods':1}
            for p in t['players']: p['minutes_last_48h'] = 40
            after = build(s,changed,b,simulations=100)['games'][0]['challenger']
            self.assertTrue(after['teams'][side]['fatigue']['back_to_back'])
            self.assertLess(after['projections'][side]['ppp'],before['projections'][side]['ppp'])
            self.assertGreater(after['projections'][side]['expected_turnovers'],before['projections'][side]['expected_turnovers'])
            shallow = team_projection(t,{})['fatigue']['rotation_load']
            for p in t['players']: p['minutes_last_48h'] = 15
            self.assertLess(team_projection(t,{})['fatigue']['rotation_load'],shallow)

    def test_missing_schedule_or_player_turnover_fails_closed(self):
        for field in ('schedule_evidence','schedule','turnover_adjustment_method'):
            s,e,b = inputs()
            del e['games']['future']['teams']['A'][field]
            self.assertIsNone(build(s,e,b,simulations=100)['games'][0]['challenger'])
        s,e,b = inputs()
        del e['games']['future']['teams']['H']['players'][0]['turnover_on_off']
        self.assertIsNone(build(s,e,b,simulations=100)['games'][0]['challenger'])

    def test_absent_defender_changes_forced_turnover_projection(self):
        t = team()
        t['players'][7]['forced_turnover_on_off'] = .15
        healthy = team_projection(t,{})
        absent = team_projection(t,{'p7':'out'})
        self.assertLess(absent['forced_turnover_rate_delta'],healthy['forced_turnover_rate_delta'])

    def test_absent_ball_handler_changes_turnover_projection(self):
        t = team()
        t['players'][7]['turnover_on_off'] = -.15
        healthy = team_projection(t,{})
        absent = team_projection(t,{'p7':'out'})
        self.assertGreater(absent['turnover_rate_delta'],healthy['turnover_rate_delta'])
        self.assertEqual(absent['players'][7]['minutes'],0)


if __name__ == '__main__': unittest.main()
