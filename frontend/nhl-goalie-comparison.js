(function(scope){
 'use strict';
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 function select(data,slate,game){
  if(data?.kind!=='nhl_goalie_ml_comparison_v1'||data.market!=='ml'||data.official!==false||data.published_baseline_replaced!==false||!Array.isArray(data.games))return null;
  if(!slate.run_id||String(slate.run_id)!==String(data.run_id)||slate.date!==data.date)return null;
  const matches=data.games.filter(r=>String(r.game_id)===String(game.game_id)&&r.home===game.home&&r.away===game.away&&r.start_utc===game.start_utc);
  if(matches.length!==1)return null;
  const row=matches[0];
  if(!finite(row.baseline_p_home)||Math.abs(row.baseline_p_home-game.ml.home)>1e-12)return null;
  if(row.status==='goalie_model_not_executed'){
   if(!Array.isArray(row.reasons)||!row.reasons.length||row.reasons.some(x=>typeof x!=='string')||['candidate_p_home','candidate_p_away','recalibration_p_home','delta_vs_baseline_pp','delta_vs_recalibration_pp'].some(k=>row[k]!==null))return null;
   return row;
  }
  if(row.status!=='experimental_goalie_ml_executed'||!row.model_sha256||!row.evidence_sha256||!row.baseline_forecast_sha256)return null;
  if(!Number.isFinite(Date.parse(row.computed_at_utc))||!Number.isFinite(Date.parse(row.baseline_as_of_utc))||!Number.isFinite(Date.parse(row.feature_as_of_utc))||Date.parse(row.feature_as_of_utc)>Date.parse(row.baseline_as_of_utc)||Date.parse(row.baseline_as_of_utc)>Date.parse(row.computed_at_utc)||Date.parse(row.computed_at_utc)>=Date.parse(row.start_utc))return null;
  if(['candidate_p_home','candidate_p_away','recalibration_p_home'].some(k=>!finite(row[k])||row[k]<0||row[k]>1))return null;
  if(Math.abs(row.candidate_p_home+row.candidate_p_away-1)>1e-6)return null;
  if(!finite(row.delta_vs_baseline_pp)||Math.abs(row.delta_vs_baseline_pp-100*(row.candidate_p_home-row.baseline_p_home))>1e-6)return null;
  if(!finite(row.delta_vs_recalibration_pp)||Math.abs(row.delta_vs_recalibration_pp-100*(row.candidate_p_home-row.recalibration_p_home))>1e-6)return null;
  return row;
 }
 function pairings(row){
  if(!Array.isArray(row?.pairings)||row.scenario_count!==row.pairings.length)return [];
  const seen=new Set(),home=new Set(),away=new Set();
  for(const p of row.pairings){
   if(['home_goalie','away_goalie'].some(k=>!Number.isInteger(p[k]?.player_id)||p[k].player_id<=0||typeof p[k].name!=='string'||!p[k].name))return [];
   const key=p.home_goalie.player_id+':'+p.away_goalie.player_id;
   if(seen.has(key)||p.home_goalie.player_id===p.away_goalie.player_id)return [];
   seen.add(key);home.add(p.home_goalie.player_id);away.add(p.away_goalie.player_id);
   if(p.status==='goalie_model_not_executed'){
    if(!Array.isArray(p.reasons)||!p.reasons.length||p.reasons.some(x=>typeof x!=='string')||['candidate_p_home','candidate_p_away','recalibration_p_home','delta_vs_baseline_pp','delta_vs_recalibration_pp'].some(k=>p[k]!==null))return [];
   }else if(p.status==='experimental_goalie_ml_executed'){
    if(!row.model_sha256||!row.scenario_history_sha256||!row.scenario_inputs_sha256||!row.baseline_forecast_sha256)return [];
    if(!Number.isFinite(Date.parse(row.baseline_as_of_utc))||!Number.isFinite(Date.parse(row.computed_at_utc))||Date.parse(row.baseline_as_of_utc)>Date.parse(row.computed_at_utc)||Date.parse(row.computed_at_utc)>=Date.parse(row.start_utc))return [];
    if(['candidate_p_home','candidate_p_away','recalibration_p_home'].some(k=>!finite(p[k])||p[k]<0||p[k]>1)||Math.abs(p.candidate_p_home+p.candidate_p_away-1)>1e-6)return [];
    if(!finite(p.delta_vs_baseline_pp)||Math.abs(p.delta_vs_baseline_pp-100*(p.candidate_p_home-row.baseline_p_home))>1e-6||!finite(p.delta_vs_recalibration_pp)||Math.abs(p.delta_vs_recalibration_pp-100*(p.candidate_p_home-p.recalibration_p_home))>1e-6)return [];
   }else return [];
  }
  return seen.size===home.size*away.size?row.pairings:[];
 }
 function reasons(row){
  if(!row)return ['No hay una comparación verificada para esta emisión.'];
  const messages=[];
  for(const reason of row.reasons||[]){
   const value=reason==='model_failed_incremental_evaluation'?'El candidato evaluado no mejoró al modelo base y no se aplica.':reason==='missing_fitted_model'?'Falta un modelo ajustado compatible con los datos actuales.':
    reason.startsWith('invalid_or_incompatible_model')?'El modelo disponible no cumple el contrato de variables.':
    reason==='missing_provider_confirmed_goalie_identity'?'Falta un arquero identificado y confirmado por el proveedor.':
    reason==='missing_prior_goalie_history'?'Falta historial previo del arquero.':
    reason==='fixture_already_started'?'El encuentro ya había comenzado al intentar el cálculo.':
    reason==='model_unavailable_at_baseline_issuance'?'El modelo todavía no estaba disponible al emitir el baseline.':
    'Falta evidencia verificada de esta emisión.';
   if(!messages.includes(value))messages.push(value);
  }
  return messages;
 }
 const api={select,reasons,pairings};
 if(typeof module!=='undefined')module.exports=api;
 if(typeof document==='undefined')return;
 let data=null;
 api.ready=fetch('./data/nhl-goalie-comparison-latest.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(value=>{data=value;}).catch(()=>{});
 const make=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
 const pct=x=>(100*x).toFixed(1).replace('.',',')+'%';
 const pp=x=>(x>0?'+':'')+x.toFixed(2).replace('.',',')+' pp';
 function appendPairings(root,row,game){
  const pairs=pairings(row);
  const unresolved=Object.entries(row?.unresolved_editorial_candidates||{}).flatMap(([team,names])=>Array.isArray(names)?names.filter(n=>typeof n==='string').map(name=>team+' · '+name):[]);
  if(!pairs.length&&!unresolved.length)return;
  const section=make('details',undefined,'nhl-goalie-pairings');section.open=true;
  section.append(make('summary','Ambos arqueros potenciales · '+pairs.length+' cruces'));
  section.append(make('p','Cada escenario supone que juega esa pareja. No se elige un titular ni se promedian los cruces.','daily-source'));
  const grid=make('div',undefined,'nhl-goalie-pair-grid');
  for(const pair of pairs){
   const card=make('article',undefined,'nhl-goalie-pair');
   for(const [team,goalie,value] of [[game.away,pair.away_goalie,pair.candidate_p_away],[game.home,pair.home_goalie,pair.candidate_p_home]]){
    const line=make('p',undefined,'nhl-goalie-pair-team');line.append(make('span',team+' · '+goalie.name),make('strong',finite(value)?pct(value):'Por calcular'));card.append(line);
   }
   if(pair.status==='experimental_goalie_ml_executed')card.append(make('p','Diferencia para '+game.home+': '+pp(pair.delta_vs_baseline_pp)+' frente a la base.','daily-source'));
   else for(const message of reasons(pair))card.append(make('p',message,'daily-source'));
   grid.append(card);
  }
  section.append(grid);
  for(const name of unresolved)section.append(make('p','Candidato pendiente de identidad: '+name,'daily-source'));
  root.append(section);
 }
 api.create=(slate,game)=>{
  const row=select(data,slate,game),root=make('section',undefined,'nhl-goalie-comparison');
  root.append(make('h5','Comparación con arquero · ganador ML'));
  if(!row||row.status!=='experimental_goalie_ml_executed'){
   root.append(make('p','Modelo con arquero no ejecutado','nhl-goalie-state'));
   for(const message of reasons(row))root.append(make('p',message,'daily-source'));
   root.append(make('p','La probabilidad de arriba usa el modelo histórico y no incorpora al arquero.','daily-source'));
   appendPairings(root,row,game);
   return root;
  }
  root.append(make('p','Candidato experimental · no reemplaza la probabilidad base','nhl-goalie-state'));
  const table=make('table',undefined,'nhl-market-table');
  const head=make('thead'),tr=make('tr');for(const label of ['Equipo','Base','Con arquero','Diferencia'])tr.append(make('th',label));head.append(tr);table.append(head);
  const body=make('tbody');
  for(const [team,base,candidate,delta] of [[game.away,1-row.baseline_p_home,row.candidate_p_away,-row.delta_vs_baseline_pp],[game.home,row.baseline_p_home,row.candidate_p_home,row.delta_vs_baseline_pp]]){
   const line=make('tr');for(const [i,value] of [team,pct(base),pct(candidate),pp(delta)].entries())line.append(make(i===0?'th':'td',value));body.append(line);
  }
  table.append(body);const scroll=make('div',undefined,'nhl-table-scroll');scroll.append(table);root.append(scroll);
  const detail=make('details');detail.append(make('summary','Qué incluye la diferencia'));
  detail.append(make('p','Incluye la recalibración del modelo. Frente al mismo control sin datos del arquero, la diferencia para '+game.home+' es '+pp(row.delta_vs_recalibration_pp)+'. No demuestra un efecto causal.','daily-source'));
  detail.append(make('p','Calculado: '+new Date(row.computed_at_utc).toLocaleString('es-CL',{timeZone:'America/Santiago',dateStyle:'short',timeStyle:'short'})+' · Chile. Solo ML; los mercados RT y +3 conservan su modelo.','daily-source'));
  root.append(detail);appendPairings(root,row,game);return root;
 };
 scope.PulsoNhlGoalieComparison=api;
})(typeof window==='undefined'?globalThis:window);
