"""Reproduce source readiness and historical assessment with existing engines.

Raw captures and frozen history are immutable inputs. Baseline retrospective
metrics never stand in for the full player/path Challenger's missing validation.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from history_store import frozen_history
from source_readiness import audit
from calibration_validation import evaluate_history, prediction_rows, markdown as calibration_markdown
from postmortem_backtest import evaluate as evaluate_candidate
from postmortem_engine import VERSION, verify_seal
from prospective import utc
from verifiable_capture import save_new, score_path


def observed_results(capture):
    """Postgame targets; source observation is earliest availability proven here."""
    root = Path(capture)
    rows = json.loads((root/'historical_boxscores.json').read_text())['games']
    results = []
    for row in rows:
        g = row['game']
        payload = json.loads((root/'sports_summaries'/(str(g['game_id'])+'.json')).read_text())
        try:
            path = score_path(payload,g)
        except (ValueError,KeyError,TypeError):
            continue  # Readiness report retains exact path rejection reasons.
        completion = payload['plays'][-1].get('wallclock')
        if not completion or not utc(g['tipoff_utc']) < utc(completion) <= utc(row['observed_at_utc']):
            raise ValueError('No reliable observed completion timestamp')
        results.append({**g,'completed_at_utc':completion,
                        'score_path_complete':True,'home_max_lead':path['home_max_lead'],
                        'away_max_lead':path['away_max_lead'],
                        'evidence':{'verified':True,'source_url':row['source_url'],
                                    'source_sha256':row['sports_payload_sha256'],
                                    'available_at_utc':row['observed_at_utc'],
                                    'observed_at_utc':row['observed_at_utc']}})
    return results


def candidate_assessment(snapshots, outcomes, historical_ids):
    """No reconstruction, fitting, probability imputation or duplicate selection."""
    for report in snapshots:
        verify_seal(report)
        if report['model_version'] != VERSION:
            raise ValueError('Candidate snapshots must use the locked V2 version')
    scored = evaluate_candidate(snapshots,outcomes)
    emitted = {str(g['game_id']) for report in snapshots for g in report['games']}
    return {'model_version':VERSION,'frozen_snapshots_supplied':len(snapshots),
            'historical_outcome_games':len(historical_ids),
            'historical_games_with_candidate_emission':len(set(historical_ids)&emitted),
            'historical_games_without_candidate_emission':len(set(historical_ids)-emitted),
            'observed_path_targets':len(outcomes),
            'evaluation':scored,
            'status':'no_eligible_candidate_predictions' if not scored['scored_ml_games'] else 'descriptive_only',
            'calibration_fit_performed':False,'independent_validation_passed':False,
            'model_hits':None,'dual':None,
            'note':'Baseline ML evaluation below is a different model. Missing candidate forecasts are not losses, successes or 50/50 probabilities.'}


def write_summary(report):
    r = report['source_readiness']; totals = r['coverage_totals']
    lines = ['# NBA — Fuentes y validación histórica', '',
             'Oficial sigue como benchmark. Challenger completo V2: investigación, PASS.', '',
             '## Cobertura de la captura', '',
             '| Evidencia | Cobertura |', '|---|---:|',
             f"| Partidos / equipos | {r['games']} / {len(r['teams'])} |",
             *[f'| {key} | {value} |' for key,value in totals.items()],
             f"| Reclamos oficiales sin identidad resuelta | {len(r['unmatched_official_claims'])} |",
             f"| Partidos aptos para el motor completo | {r['model_ready_games']} |", '',
             'Las fuentes de titulares proyectados no certifican IDs ni disponibilidad completa.',
             'Minutos observados y posesiones estimadas no son proyecciones ni posesiones normalizadas.', '',
             '## Evaluación retrospectiva ejecutada', '',
             '| Modelo / temporada final | n | Brier | Log loss | ECE |', '|---|---:|---:|---:|---:|']
    for label,group in report['baseline_calibration']['groups'].items():
        for model in ('elo','challenger'):
            m=group[model];name='Oficial Elo' if model=='elo' else 'Baseline margen/descanso (no V2)'
            lines.append(f"| {name} / {label} | {m['n']} | {m['brier']:.6f} | {m['log_loss']:.6f} | {m['ece_10_equal_width']:.6f} |")
    candidate=report['full_candidate']
    lines += ['',f"Challenger V2: {candidate['evaluation']['scored_ml_games']} partidos puntuados; no se ajustó calibrador.",
              'ML/+20 sin pronósticos elegibles: Brier/log loss NULL, sin aciertos ni DUAL.',
              'Este recorrido usa resultados anteriores, pero las temporadas ya fueron inspeccionadas: no acredita independencia de selección.', '',
              '## Trayectorias observadas, sin predicciones retrospectivas', '',
              '| Partido | Resultado | Máxima local / visitante |', '|---|---|---|']
    for g in report['observed_results']:
        lines.append(f"| {g['away_team']} @ {g['home_team']} | {g['away_points']}–{g['home_points']} | {g['home_max_lead']} / {g['away_max_lead']} |")
    lines += ['', '## Bloqueos por equipo', '', '| Requisito | Equipos bloqueados |','|---|---:|',
              *[f'| {key} | {value} |' for key,value in r['blocking_requirement_counts'].items()], '',
              'Próximas entradas necesarias: export autorizado de posesiones y alineaciones, efectos ajustados de jugadores con fecha de corte, roles/reemplazos, minutos/uso proyectados, carga y calendario completos.',
              'No se sustituyen con on/off crudo, promedios de minutos o datos recuperados después del partido.', '',
              'Fuentes: [NBA Injury Reports](https://official.nba.com/nba-injury-report-2026-27-season), [NBA Stats Glossary](https://www.nba.com/stats/help/glossary), ESPN (URLs y hashes exactos en la captura).',
              'Sin cuotas como entradas. Sin promoción automática ni merge.', '']
    return '\n'.join(lines)


def run(capture, archive, output, snapshot_paths=(), repetitions=2000):
    root=Path(output)
    root.mkdir(parents=True,exist_ok=False)
    readiness=audit(capture)
    history,provenance=frozen_history(archive)
    baseline=evaluate_history(history,repetitions=repetitions)
    results=observed_results(capture)
    snapshots=[json.loads(Path(p).read_text()) for p in snapshot_paths]
    candidate=candidate_assessment(snapshots,results,[str(g['game_id']) for g in history if int(g['season']) in (2025,2026)])
    report={'schema_version':1,'created_at_utc':datetime.now(timezone.utc).isoformat(),
            'source_readiness':readiness,'history_provenance':provenance,
            'baseline_model_identity':{'elo':'Official Elo benchmark',
                                       'challenger':'Legacy rolling margin/rest baseline; NOT full Challenger 2026-27.1 V2'},
            'baseline_calibration':baseline,'full_candidate':candidate,
            'observed_results':results,'production_approved':False,'no_odds_input':True}
    save_new(root,'assessment.json',report)
    save_new(root,'candidate-evaluation.json',candidate)
    save_new(root,'verified-postgame-results.json',results)
    save_new(root,'source-readiness.json',readiness)
    save_new(root,'baseline-calibration.json',baseline)
    save_new(root,'baseline-retrospective-predictions.json',
             {'emission_kind':'retrospective_replay','created_at_utc':report['created_at_utc'],
              'models':report['baseline_model_identity'],'rows':prediction_rows(history),
              'not_pregame_archived_predictions':True})
    with (root/'RESULTADO.md').open('x') as f:f.write(write_summary(report))
    with (root/'baseline-calibration.md').open('x') as f:f.write(calibration_markdown(baseline))
    # Snapshot/code identity is explicit; no retrospective claim of preregistration.
    code={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
          for name in ('model.py','challenger.py','postmortem_engine.py','score_path.py',
                       'possession_path_features.py','source_readiness.py','data_validation_run.py',
                       'postmortem_backtest.py','calibration_validation.py','verifiable_capture.py',
                       'possession_intelligence.py')}
    save_new(root,'run-provenance.json',{'created_at_utc':report['created_at_utc'],
             'code_sha256':code,'source_manifest_sha256':readiness['source_manifest_sha256'],
             'frozen_history_sha256':provenance['archive_history_sha256'],
             'candidate_snapshot_sha256':[s['content_sha256'] for s in snapshots],
             'independent_pretip_registration':False})
    save_new(root,'manifest.json',{'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(root.iterdir()) if p.is_file()}})
    return report


def main():
    p=argparse.ArgumentParser()
    for name in ('capture','archive','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--candidate-snapshots',nargs='*',default=[])
    p.add_argument('--repetitions',type=int,default=2000)
    a=p.parse_args()
    r=run(a.capture,a.archive,a.output,a.candidate_snapshots,a.repetitions)
    print(json.dumps({'source_ready_games':r['source_readiness']['model_ready_games'],
                      'baseline_scored_games':r['baseline_calibration']['scored_games'],
                      'candidate_scored_games':r['full_candidate']['evaluation']['scored_ml_games']}))


if __name__=='__main__':main()
