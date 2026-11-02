import json
import unittest
from datetime import datetime, timezone
from nhl.match_context import build, editorial

NOW = datetime(2026,11,2,20,tzinfo=timezone.utc)
GAME = dict(id='2026020232', home='BOS', away='VGK', home_name='Bruins', away_name='Golden Knights', start_utc='2026-11-03T00:00:00Z', venue='TD Garden')


def article(date='2026-11-02T19:00:00Z'):
    text = '<script type="application/ld+json">'+json.dumps({'@type':'NewsArticle','dateModified':date})+'</script>'
    for team in ('Bruins','Golden Knights'):
        text += '<h3>'+team+' projected lineup</h3>'
        text += ''.join('<p>A -- B -- C</p>' for _ in range(4))
        text += ''.join('<p>D — E</p>' for _ in range(3))
        text += '<p>Goalie One</p><p>Goalie Two</p><p>Scratched: Bench Player</p><p>Injured: Injured Player (knee)</p><p>Status report</p><p>Do not import this prose</p>'
    return text.encode()


def get(url):
    if url.endswith('landing'):
        return json.dumps(dict(id=2026020232, homeTeam={'abbrev':'BOS'}, awayTeam={'abbrev':'VGK'}, startTimeUTC=GAME['start_utc'], venue={'default':'TD Garden'}, venueLocation={'default':'Boston'})).encode()
    return json.dumps({'gameInfo':{'referees':[{'name':{'default':'Ref One'}}], 'linesmen':[]}}).encode()


class MatchContextTests(unittest.TestCase):
    def test_projected_lines_no_invented_starter_and_officials(self):
        result=build({'games':[GAME]}, article(), get, NOW)
        row=result['games'][0]; team=row['teams']['BOS']
        self.assertEqual(len(team['forwards']),4)
        self.assertEqual(len(team['defense']),3)
        self.assertEqual(team['goalies'],['Goalie One','Goalie Two'])
        self.assertIsNone(team['starting_goalie'])
        self.assertEqual(row['referees'],['Ref One'])
        self.assertEqual(row['linesmen'],[])
        self.assertEqual(row['city'],'Boston')
        self.assertEqual(team['injuries'],['Injured Player (knee)'])
        self.assertFalse(result['model_features_used'])

    def test_stale_future_and_wrong_team_article_rejected(self):
        for raw in (article('2026-11-01T19:00:00Z'), article('2026-11-03T19:00:00Z'), article().replace(b'Bruins',b'Other')):
            row=build({'games':[GAME]},raw,get,NOW)['games'][0]
            self.assertEqual(row['teams'],{})
            self.assertEqual(row['venue'],'TD Garden')

    def test_started_game_does_not_fetch_postgame_as_pregame(self):
        def fail(url): self.fail('Should not fetch started fixture')
        row=build({'games':[dict(GAME,start_utc='2026-11-02T19:00:00Z')]},article(),fail,NOW)['games'][0]
        self.assertEqual(row['teams'],{})
        self.assertTrue(row['errors'])

    def test_source_failure_and_mismatch_keep_missing_explicit(self):
        def fail(url): raise ValueError('Source unavailable')
        row=build({'games':[GAME]},b'',fail,NOW)['games'][0]
        self.assertEqual(row['referees'],[])
        self.assertEqual(row['teams'],{})
        self.assertEqual(len(row['errors']),2)
        def mismatch(url): return get(url).replace(b'2026020232',b'2026020233')
        row=build({'games':[GAME]},article(),mismatch,NOW)['games'][0]
        self.assertIn('landing unavailable or invalid',row['errors'])

    def test_empty_injuries_distinct_from_missing(self):
        _,blocks=editorial(article().replace(b'Injured Player (knee)',b'None'),NOW)
        self.assertEqual(blocks['bruins']['injuries'],[])
        _,blocks=editorial(article().replace(b'<p>Injured: Injured Player (knee)</p>',b''),NOW)
        self.assertIsNone(blocks['bruins']['injuries'])
