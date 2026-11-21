(function(scope){
 'use strict';
 const api={snapshot:null,ready:Promise.resolve()};
 if(typeof document==='undefined'){scope.PulsoNhlInputs=api;return;}
 api.ready=fetch('./data/nhl-pregame-inputs-latest.json',{cache:'no-store'})
  .then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();})
  .then(data=>{if(data.kind!=='nhl_pregame_input_inventory_v1'||!Array.isArray(data.games))throw Error('Invalid inventory');api.snapshot=data;})
  .catch(()=>{});
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const pretty=value=>{
  if(value===null||value===undefined)return '—';
  if(typeof value==='string'||typeof value==='number'||typeof value==='boolean')return String(value);
  if(Array.isArray(value))return value.map(v=>typeof v==='object'&&v?(v.name||v.resolved_name||'jugador')+([v.position_observation,v.reported_status].filter(Boolean).length?' ('+[v.position_observation,v.reported_status].filter(Boolean).join(', ')+')':''):pretty(v)).join(' · ');
  if(value.model_effect){const effect=value.model_effect;const teams=value.teams?pretty(value.teams):null;const applied='Efecto: '+(effect.status||'sin aplicar')+(Number.isFinite(effect.probability_delta_home_percentage_points)?' · cambio ML '+effect.probability_delta_home_percentage_points.toFixed(2)+' pp':'')+(Number.isFinite(effect.probability_delta_percentage_points)?' · cambio '+effect.probability_delta_percentage_points.toFixed(2)+' pp':'')+(effect.reason?' · '+effect.reason:'');return [teams,applied].filter(Boolean).join(' | ');}
  if(value.players&&Array.isArray(value.players))return value.players.map(p=>(p.resolved_name||p.name||'jugador')+(p.position_observation?' · '+p.position_observation:'')+(p.reported_status?' · '+p.reported_status:'')).join(' · ')||'Sin jugadores listados';
  if(value.teams&&typeof value.teams==='object')return Object.entries(value.teams).map(([team,side])=>{
   if(!side)return team+': sin dato';
   if(side.status==='conditional_replacement_scenario')return team+': escenario disponible · '+Number(side.lost_minutes||0).toFixed(1)+' min fuera · '+Number(side.allocated_minutes||0).toFixed(1)+' min redistribuidos';
   if(side.status)return team+': '+side.status+(side.back_to_back===true?' · B2B':'')+(Number.isFinite(side.rest_days_before_game)?' · '+side.rest_days_before_game+' días descanso':'')+(side.hours_between_starts?' · '+Math.round(side.hours_between_starts)+' h entre partidos':'');
   return team+': '+Object.entries(side).filter(([k,v])=>v!==null&&typeof v!=='object').map(([k,v])=>k.replaceAll('_',' ')+': '+v).join(', ');
  }).join(' | ');
  return Object.entries(value).filter(([k,v])=>v!==null&&typeof v!=='object'&&!['player_id','sha256_etiquetas'].includes(k)).map(([k,v])=>k.replaceAll('_',' ')+': '+v).join(' | ');
 };
 function valueText(row){
  const v=row.value;if(!v)return '—';
  if(v.projected_lines)return v.projected_lines.map((line,i)=>'L'+(i+1)+': '+line.map(p=>typeof p==='string'?p:p.name).join(' · ')).join(' | ');
  if(v.projected_pairs)return v.projected_pairs.map((line,i)=>'P'+(i+1)+': '+line.map(p=>typeof p==='string'?p:p.name).join(' · ')).join(' | ');
  if(v.source_grouping&&v.players!==undefined)return [v.team,v.players===null?'sin lista':pretty(v.players),v.source_grouping].filter(Boolean).join(' · ');
  if(v.candidatos)return [v.team+': '+(v.candidatos.join(' / ')||'sin candidatos'),v.provider_status?'estado del proveedor: '+v.provider_status:null,v.confirmacion_independiente?'confirmación independiente':'sin confirmación independiente'].filter(Boolean).join(' · ');
  if(v.lesionados_reportados!==undefined)return v.team+': lesionados '+(v.lesionados_reportados===null?'sin dato':v.lesionados_reportados.length===0?'sin nombres en la fuente':pretty(v.lesionados_reportados))+'; descartados '+(v.descartados_reportados===null?'sin dato':pretty(v.descartados_reportados)||'ninguno');
  if(v.start_utc)return 'Inicio: '+new Date(v.start_utc).toLocaleString('es-CL',{timeZone:'America/Santiago',dateStyle:'medium',timeStyle:'short'})+' · Recinto: '+(v.venue||'pendiente');
  if(v.juegos_historicos_previos!==undefined)return [v.modelo,v.juegos_historicos_previos+' partidos previos',v.fecha_emision].filter(Boolean).join(' · ');
  return pretty(v);
 }
 api.create=game=>{
  const record=api.snapshot?.games.find(g=>String(g.game_id)===String(game.game_id)&&g.home===game.home&&g.away===game.away&&g.start_utc===game.start_utc);
  const root=el('details',undefined,'nhl-pregame-input-inventory');
  if(!record){root.append(el('summary','Entradas pregame · auditoría no publicada'));root.append(el('p','Esta captura todavía no tiene el inventario de fuentes. Ejecuta una nueva corrida para generar la ficha.','nhl-input-note'));return root;}
  const summary=el('summary',`Entradas de la predicción · ${record.captured_count} capturadas · ${record.missing_count} por buscar`);
  root.append(summary,el('p','Cada fila indica qué se capturó, qué falta y si esta ejecución aplicó un efecto al porcentaje. Las fuentes sugeridas sirven para buscar la información y solicitar una nueva corrida.','nhl-input-note'));
  const retry=el('a','Buscar datos y volver a ejecutar en GitHub Actions','nhl-input-retry');
  retry.href='https://github.com/amante/BeatBetano/actions/workflows/pulso-nhl-prospective.yml';retry.target='_blank';retry.rel='noopener noreferrer';root.append(retry);
  for(const group of record.groups){
   const section=el('details',undefined,'nhl-input-group');const missing=group.rows.filter(r=>r.status!=='captured').length;
   section.append(el('summary',group.title+(missing?' · '+missing+' pendiente'+(missing===1?'':'s'):'')));
   const list=el('div',undefined,'nhl-input-list');
   for(const row of group.rows){
    const item=el('article',undefined,'nhl-input-row nhl-input-'+row.status);
    const top=el('div',undefined,'nhl-input-row-top');top.append(el('strong',row.label),el('span',({captured:'Capturado',partial:'Incompleto',missing:'Falta capturar',blocked:'Bloqueado'})[row.status]||'Revisar','nhl-input-state'));item.append(top);
    item.append(el('p',valueText(row),'nhl-input-value'));
    const use=el('p',undefined,'nhl-input-use');use.append(el('span',row.used_in_base_probability?'Incluido en el cálculo':'No afecta el porcentaje base',row.used_in_base_probability?'nhl-input-used':'nhl-input-context'),document.createTextNode(' '+row.use_note));item.append(use);
    if(row.gap)item.append(el('p','Pendiente: '+row.gap,'nhl-input-gap'));
    const url=row.source?.url;
    if(url&&/^https:\/\//.test(url)){const link=el('a','Fuente capturada');link.href=url;link.target='_blank';link.rel='noopener noreferrer';item.append(link);}
    else if(url)item.append(el('small','Registro: '+url));
    if(row.suggested_source_url){const link=el('a','Revisar fuente sugerida');link.href=row.suggested_source_url;link.target='_blank';link.rel='noopener noreferrer';link.className='nhl-input-suggested';item.append(link);}
    if(row.source?.captured_at_utc){const time=el('small','Captura: '+row.source.captured_at_utc);item.append(time);}
    list.append(item);
   }
   section.append(list);root.append(section);
  }
  root.append(el('p','Una nueva corrida crea un registro nuevo con la información disponible en ese momento; no reescribe esta captura.','nhl-input-note'));
  return root;
 };
 scope.PulsoNhlInputs=api;
})(typeof window==='undefined'?globalThis:window);
