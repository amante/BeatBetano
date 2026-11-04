"""Odds-free, two-sided NBA research report; unsupported quantities stay PASS.

Schedule adjustment is a descriptive leave-one-game-out residual estimator,
not a fitted causal availability model or a calibrated probability forecast.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from datetime import datetime, timezone


def utc(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() != timezone.utc.utcoffset(result):
        raise ValueError('Explicit UTC timestamp required')
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def adjusted_ratings(boxscores, cutoff, minimum=3):
    """Estimate schedule residuals using only complete paired prior observations.

    Common game possessions = mean of the two boxscore estimates. League and
    opponent ratings are possession-weighted. Opponent baselines exclude the
    game being adjusted. This is one-step adjustment, not recursive regression.
    """
    cutoff = utc(cutoff)
    pairs = []
    seen = set()
    for row in boxscores.get('games', []):
        g = row['game']
        gid = str(g['game_id'])
        if gid in seen:
            raise ValueError('Duplicate boxscore game')
        seen.add(gid)
        if utc(g['tipoff_utc']) >= cutoff or utc(row['observed_at_utc']) > cutoff:
            continue
        h, a = g['home_team'], g['away_team']
        stats = row['team_statistics']
        if set(stats) != {h, a} or h == a:
            raise ValueError('Boxscore team identity mismatch')
        for team in (h, a):
            for field in ('points', 'possessions_estimated'):
                x = stats[team][field]
                if type(x) not in (int, float) or not math.isfinite(x) or x <= 0:
                    raise ValueError('Invalid boxscore numeric value')
            if stats[team]['points'] != g['home_points' if team == h else 'away_points']:
                raise ValueError('Boxscore points mismatch')
        poss = sum(stats[t]['possessions_estimated'] for t in (h, a)) / 2
        for team, opp in ((h, a), (a, h)):
            pairs.append({'game_id': gid, 'team': team, 'opponent': opp, 'poss': poss,
                          'points': stats[team]['points'], 'allowed': stats[opp]['points']})
    if not pairs:
        return {}
    league = 100 * sum(r['points'] for r in pairs) / sum(r['poss'] for r in pairs)
    teams = {r['team'] for r in pairs}
    result = {}
    for team in sorted(teams):
        own = [r for r in pairs if r['team'] == team]
        adjustments = []
        for r in own:
            opp = [s for s in pairs if s['team'] == r['opponent'] and s['game_id'] != r['game_id']]
            if len(opp) < minimum - 1:
                continue
            denom = sum(s['poss'] for s in opp)
            opp_o = 100 * sum(s['points'] for s in opp) / denom
            opp_d = 100 * sum(s['allowed'] for s in opp) / denom
            adjustments.append((r, 100*r['points']/r['poss'] - opp_d,
                                100*r['allowed']/r['poss'] - opp_o))
        poss = sum(r['poss'] for r in own)
        usable = len(adjustments) >= minimum
        weight = sum(r['poss'] for r, _, _ in adjustments)
        result[team] = {
            'sample_games': len(own), 'adjustable_games': len(adjustments),
            'league_rating': league,
            'raw_ortg': 100*sum(r['points'] for r in own)/poss,
            'raw_drtg': 100*sum(r['allowed'] for r in own)/poss,
            'opponent_adjusted_ortg': league + sum(r['poss']*o for r,o,d in adjustments)/weight if usable else None,
            'opponent_adjusted_drtg': league + sum(r['poss']*d for r,o,d in adjustments)/weight if usable else None,
            'historical_possessions_per_game': poss/len(own),
            'status': 'descriptive_schedule_adjusted' if usable else 'PASS_insufficient_opponent_sample',
            'game_ids': [r['game_id'] for r in own],
        }
    return result


def build(snapshot, boxscores, roster=None, lineups=None, availability=None, minutes=None, scenarios=None):
    check = {k:v for k,v in snapshot.items() if k != 'content_sha256'}
    if digest(check) != snapshot.get('content_sha256'):
        raise ValueError('Snapshot hash mismatch')
    created = utc(snapshot['created_at_utc'])
    optional = [roster, lineups, availability, minutes, scenarios]
    for item in optional:
        if item is not None and item.get('snapshot_sha256') != snapshot['content_sha256']:
            raise ValueError('Evidence snapshot mismatch')
    def validate_times(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ('observed_at_utc', 'input_observed_at_utc', 'collected_at_utc') and v is not None:
                    if utc(v) > created:
                        raise ValueError('Evidence collected after frozen snapshot')
                else:
                    validate_times(v)
        elif isinstance(node, list):
            for item in node:
                validate_times(item)
    for item in optional:
        if item is not None:
            validate_times(item)
    ratings = adjusted_ratings(boxscores, snapshot['created_at_utc'])
    output = []
    ids = set()
    for g in snapshot['predictions']:
        gid = str(g['game_id'])
        if gid in ids or g['home_team'] == g['away_team']:
            raise ValueError('Duplicate or invalid fixture')
        ids.add(gid)
        if {'NY', 'NYK'} & {g['home_team'], g['away_team']}:
            raise ValueError('Knicks excluded from this slate')
        if utc(g['tipoff_utc']) <= created:
            raise ValueError('Snapshot is not pregame')
        teams = {}
        for team, opp in ((g['home_team'], g['away_team']), (g['away_team'], g['home_team'])):
            stats, rival = ratings.get(team, {}), ratings.get(opp, {})
            def evidence(document):
                return (document or {}).get('games', {}).get(gid, {}).get('teams', {}).get(team, {})
            members = evidence(roster)
            current = evidence(availability)
            allocation = evidence(minutes)
            candidate = evidence(lineups)
            branches = evidence(scenarios)
            statuses = {p['player_id']:p for p in current.get('players', [])}
            allocations = allocation.get('allocations')
            if allocations is not None:
                if set(allocations) != {p['player_id'] for p in members.get('players', [])}:
                    raise ValueError('Minutes omit roster members')
                if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=48 for v in allocations.values()) or abs(sum(allocations.values())-240) > .001:
                    raise ValueError('Invalid regulation minute budget')
            player_ids = [p['player_id'] for p in members.get('players', [])]
            if len(player_ids) != len(set(player_ids)):
                raise ValueError('Duplicate roster player')
            players = []
            for p in members.get('players', []):
                prior = []
                for row in boxscores.get('games', []):
                    if utc(row['game']['tipoff_utc']) >= created or utc(row['observed_at_utc']) > created:
                        continue
                    for old in row.get('players', []):
                        if old['team'] == team and old['player_id'] == p['player_id'] and not old['did_not_play'] and type(old['minutes_played']) in (int,float):
                            prior.append((utc(row['game']['tipoff_utc']), old['minutes_played']))
                vals = [v for _,v in sorted(prior)[-5:]]
                players.append({**p, 'availability': statuses.get(p['player_id'], {}).get('status', 'unknown'),
                    'lineup_role': 'provider_starting_five' if p['player'] in candidate.get('starters', []) else 'unconfirmed_role',
                    'historical_sample_games': len(prior),
                    'historical_mean_last_five_minutes': sum(vals)/len(vals) if len(vals)>=3 else None,
                    'projected_minutes': allocations.get(p['player_id']) if allocations is not None else None})
            o, d = stats.get('opponent_adjusted_ortg'), rival.get('opponent_adjusted_drtg')
            possession_values = [r.get('historical_possessions_per_game') for r in (stats, rival)]
            possessions = sum(possession_values)/2 if all(v is not None for v in possession_values) and all(r.get('sample_games',0)>=3 for r in (stats,rival)) else None
            ppp = (o+d)/200 if o is not None and d is not None else None
            teams[team] = {
                'historical_ratings': stats,
                'availability_adjusted_ortg': None, 'availability_adjusted_drtg': None,
                'research_projected_possessions': possessions,
                'research_matchup_ppp': ppp,
                'research_projected_points': possessions*ppp if possessions is not None and ppp is not None else None,
                'lineup_status': candidate.get('lineup_status', 'unavailable'),
                'provider_starters': candidate.get('starters', []), 'players': players,
                'minutes_status': allocation.get('status','PASS_missing_availability'),
                'on_off_scenarios': branches,
                'injury_replacement_impact': {'status':'PASS_no_validated_player_and_interaction_coefficients',
                    'offense_delta_per_100':None, 'defense_delta_per_100':None,
                    'ml_delta':None, 'reach_plus20_delta':None},
                'final_ml_probability':None, 'reach_plus20_probability':None,
                'status':'PASS',
            }
        baseline = {}
        for label, key in (('Official_Elo_benchmark', 'elo_p_home'), ('Challenger_margin_rest_experimental', 'challenger_p_home')):
            p = g.get(key)
            if type(p) not in (int,float) or not math.isfinite(p) or not 0<p<1:
                raise ValueError('Invalid executed baseline probability')
            baseline[label] = {'home_ml':p,'away_ml':1-p,'calibrated_full_model':False,
                               'home_reach_plus20':None,'away_reach_plus20':None}
        output.append({'game_id':gid,'tipoff_utc':g['tipoff_utc'],'home_team':g['home_team'],
                       'away_team':g['away_team'],'teams':teams,'executed_baselines':baseline,
                       'status':'PASS_full_model_incomplete',
                       'missing':['validated_availability_and_replacement_effects','complete_verified_minutes_and_roles',
                                  'validated_in_game_lead_path_model'],
                       'challenger_minus_official_home_ml':g['challenger_p_home']-g['elo_p_home']})
    return {'schema_version':1,'created_at_utc':snapshot['created_at_utc'],
            'snapshot_sha256':snapshot['content_sha256'],'boxscores_sha256':digest(boxscores),
            'no_odds_input':True,'games_count':len(output),'games':output,
            'full_model_complete':False,'independent_holdout_validation_passed':False,
            'method':'leave_one_game_out_opponent_residual_v1',
            'limitations':['Research rates are descriptive, not independently calibrated forecasts.',
                'Availability-adjusted ratings require player replacement and interaction effects; remain null.',
                'Pace heuristic averages observed game possessions; overtime is not normalized.',
                'Both teams can reach +20 in one game; these probabilities are not complements.',
                'Full-model PASS does not suppress executed Elo/Challenger benchmark diagnostics.']}


def markdown(report):
    lines = ['# NBA 2026-27 — informe reproducible del 4 de noviembre', '',
             'Knicks excluido. Modelo completo: **PASS en todos los partidos**. Sin cuotas como entrada.',
             'Elo y Challenger son referencias ejecutadas; no son el modelo deportivo completo ni están certificados como calibrados.', '',
             '| Partido | Elo ML local / visita | Challenger ML local / visita | +20 local / visita | Estado |',
             '|---|---:|---:|---|---|']
    for g in report['games']:
        b=list(g['executed_baselines'].values())
        lines.append(f"| {g['away_team']} @ {g['home_team']} | {b[0]['home_ml']:.2%} / {b[0]['away_ml']:.2%} | {b[1]['home_ml']:.2%} / {b[1]['away_ml']:.2%} | PASS / PASS | PASS |")
    for g in report['games']:
        lines += ['', f"## {g['away_team']} @ {g['home_team']}", '',
                  '| Equipo | n | ORtg rival ajustado* | DRtg rival ajustado* | Posesiones* | PPP* | ORtg/DRtg disponibilidad |',
                  '|---|---:|---:|---:|---:|---:|---|']
        fmt=lambda v: 'PASS' if v is None else f'{v:.3f}'
        for team, t in g['teams'].items():
            r=t['historical_ratings']
            lines.append(f"| {team} | {r.get('sample_games',0)} | {fmt(r.get('opponent_adjusted_ortg'))} | {fmt(r.get('opponent_adjusted_drtg'))} | {fmt(t['research_projected_possessions'])} | {fmt(t['research_matchup_ppp'])} | PASS / PASS |")
        for team,t in g['teams'].items():
            lines += ['',f"### {team}: plantilla completa observada",'',
                      f"Quinteto del proveedor ({t['lineup_status']}): {', '.join(t['provider_starters']) or 'PASS'}. Minutos: {t['minutes_status']}.", '',
                      '| Jugador | Estado observado | Media histórica (últimos 5; mínimo 3) | Minutos proyectados |',
                      '|---|---|---:|---:|']
            for p in t['players']:
                lines.append(f"| {p['player']} | {p['availability']} | {fmt(p['historical_mean_last_five_minutes'])} | {fmt(p['projected_minutes'])} |")
            if not t['players']:lines.append('| PASS: plantilla no disponible | unknown | PASS | PASS |')
            lines += ['', 'Injury × Replacement Impact: PASS; faltan coeficientes de jugadores, reemplazos e interacciones validados.',
                      'Escenarios on/off: '+ t['on_off_scenarios'].get('status','PASS_missing_evidence')+'. Sin ponderaciones ni probabilidades inventadas.']
    lines += ['', '*Estimadores exploratorios documentados en nba/REPRODUCIBLE_SLATE.md; no incorporan disponibilidad.*', '',
              'Snapshot: '+report['snapshot_sha256']+'; captura UTC: '+report['created_at_utc'], '']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser()
    for name in ('snapshot','boxscores','output','summary'):p.add_argument('--'+name,required=True)
    for name in ('roster','lineups','availability','minutes','scenarios'):p.add_argument('--'+name)
    a=p.parse_args()
    load=lambda f:json.loads(Path(f).read_text()) if f else None
    report=build(load(a.snapshot),load(a.boxscores),**{k:load(getattr(a,k)) for k in ('roster','lineups','availability','minutes','scenarios')})
    for path,body in ((a.output,json.dumps(report,indent=2,allow_nan=False)),(a.summary,markdown(report))):
        with Path(path).open('x') as f:f.write(body)
    print(json.dumps({'games':report['games_count'],'full_model_complete':False}))

if __name__=='__main__':main()
