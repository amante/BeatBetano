import copy
import unittest
from nhl.schedule_context import team_context,collect

F=dict(game_id='2026020232',home='BOS',away='VGK',start_utc='2026-11-03T00:00:00Z')

def payload():
 return {'games':[dict(id=2026020231,gameDate='2026-11-01',startTimeUTC='2026-11-02T00:00:00Z',gameState='OFF',gameScheduleState='OK',venue={'default':'Arena A'},homeTeam={'abbrev':'BOS'},awayTeam={'abbrev':'MTL'}),dict(id=2026020232,gameDate='2026-11-02',startTimeUTC=F['start_utc'],gameState='FUT',venue={'default':'Arena B'},homeTeam={'abbrev':'BOS'},awayTeam={'abbrev':'VGK'})]}


class ScheduleContext(unittest.TestCase):
 def test_gap_b2b_and_venue_are_observed_but_actual_rest_and_travel_unknown(self):
  r=team_context('BOS',payload(),F,'2026-11-02T20:00:00Z')
  self.assertEqual(r['hours_between_starts'],24)
  self.assertTrue(r['back_to_back']);self.assertTrue(r['venue_changed'])
  self.assertIsNone(r['travel_km']);self.assertIsNone(r['actual_rest_hours'])
  self.assertFalse(r['applied_to_probability'])

 def test_unplayed_intervening_game_is_not_actual_workload(self):
  d=payload();d['games'][0]['gameState']='FUT';d['games'][0]['startTimeUTC']='2026-11-02T22:00:00Z'
  r=team_context('BOS',d,F,'2026-11-02T20:00:00Z')
  self.assertEqual(r['status'],'planned_previous_fixture_not_completed')

 def test_changed_start_and_started_target_rejected(self):
  d=payload();d['games'][1]['startTimeUTC']='2026-11-03T02:00:00Z'
  with self.assertRaises(ValueError):team_context('BOS',d,F,'2026-11-02T20:00:00Z')
  with self.assertRaises(ValueError):team_context('BOS',payload(),F,'2026-11-03T01:00:00Z')

 def test_missing_previous_fixture_and_postponement_remain_explicit(self):
  d=payload();d['games'][0]['gameScheduleState']='PPD'
  r=team_context('BOS',d,F,'2026-11-02T20:00:00Z')
  self.assertEqual(r['status'],'missing_previous_fixture')
  self.assertIsNone(r['back_to_back'])

 def test_core_consumes_schedule_context_only_before_analysis_cutoff(self):
  from nhl.pulso_sporting_core_245 import integrate
  report=dict(data_kind='source_readiness_only',official_predictions=0,generated_at_utc='2026-11-02T19:00:00Z',games=[F])
  g=dict(F,as_of='2026-11-02T20:10:00Z',teams={t:dict(roster_identity_available=True,provider_goalie_id_observed=None,goalie_confirmed_independently=False) for t in ('BOS','VGK')})
  b=dict(kind='sporting_source_bridge',as_of=g['as_of'],games={F['game_id']:g})
  schedules={t:payload() for t in ('BOS','VGK')}
  schedules['VGK']['games'][0]['awayTeam']['abbrev']='VGK'
  sides={t:team_context(t,schedules[t],F,'2026-11-02T20:00:00Z') for t in ('BOS','VGK')}
  ctx=dict(kind='nhl_official_schedule_context_v1',source_capture_as_of=report['generated_at_utc'],as_of_utc='2026-11-02T20:00:00Z',games=[dict(F,teams=sides)])
  r=integrate(report,b,{},schedule_context=ctx)['games'][0]
  self.assertTrue(r['module_manifest']['venue_rest_travel']['observed'])
  self.assertFalse(r['module_manifest']['venue_rest_travel']['applied_to_sporting_probability'])
  ctx['as_of_utc']='2026-11-02T20:11:00Z'
  with self.assertRaises(ValueError):integrate(report,b,{},schedule_context=ctx)

 def test_foreign_team_prior_is_not_attributed_as_rest(self):
  r=team_context('VGK',payload(),F,'2026-11-02T20:00:00Z')
  self.assertEqual(r['status'],'missing_previous_fixture')
