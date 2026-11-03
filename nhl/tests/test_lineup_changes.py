import unittest
from nhl.lineup_changes import build
class ChangesTests(unittest.TestCase):
 def inputs(self):
  players=[dict(player_id=i,name=str(i)) for i in range(1,19)]
  side=dict(projected_skaters_identity_complete=True,projected=dict(forwards=[players[:12]],defense=[players[12:]],injuries=[],scratches=[]))
  e=dict(kind='nhl_pregame_player_evidence_v1',games=[dict(game_id='1',start_utc='2026-11-03T00:00:00Z',feature_as_of_utc='2026-11-02T20:00:00Z',teams=dict(BOS=side))])
  r=dict(kind='nhl_prior_lineup_reference_v1',games=[dict(game_id='1',teams=dict(BOS=dict(players=[dict(player_id=i,name=str(i),role='forward',observed_toi_seconds=100) for i in range(2,20)],source=dict(retrieved_at='2026-11-02T20:01:00Z'))))])
  h=dict(kind='nhl_skater_history_capture_v1',cutoff_exclusive='2026-11-02',players={})
  return e,r,h
 def test_changes_and_missing_are_explicit(self):
  x=build(*self.inputs())['games'][0]['teams']['BOS'];self.assertEqual(x['out_of_projection'][0]['player_id'],19);self.assertEqual(x['new_in_projection'][0]['player_id'],1);self.assertEqual(len(x['missing_history_ids']),19);self.assertFalse(x['applied_to_probability'])
 def test_incomplete_is_blocked(self):
  e,r,h=self.inputs();e['games'][0]['teams']['BOS']['projected_skaters_identity_complete']=False
  self.assertEqual(build(e,r,h)['games'][0]['teams']['BOS']['status'],'blocked')
 def test_late_history_rejected(self):
  e,r,h=self.inputs();h['players']['1']=dict(cutoff_exclusive='2026-11-02',source=dict(retrieved_at='2026-11-03T00:00:00Z'))
  with self.assertRaises(ValueError):build(e,r,h)
 def test_duplicate_projected_player_rejected(self):
  e,r,h=self.inputs();e['games'][0]['teams']['BOS']['projected']['defense'][0][0]['player_id']=1
  with self.assertRaises(ValueError):build(e,r,h)
