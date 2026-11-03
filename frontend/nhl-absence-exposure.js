(function(scope){
'use strict';let snapshot=null;const api={};
const make=(tag,text)=>{const x=document.createElement(tag);if(text!==undefined)x.textContent=text;return x;};
const number=v=>Number.isFinite(v)?v.toFixed(2).replace('.',','):'Sin dato';
api.ready=fetch('./data/nhl-absence-exposure.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(x=>{if(x.kind!=='nhl_absence_exposure_v1')throw Error();snapshot=x;}).catch(()=>{});
api.create=game=>{
 const root=make('details');root.className='nhl-absence-exposure';root.append(make('summary','Bajas, reemplazos y reparto de minutos'));
 const matches=(snapshot?.games||[]).filter(g=>String(g.game_id)===String(game.game_id)&&g.home===game.home&&g.away===game.away&&g.start_utc===game.start_utc);
 if(matches.length!==1||!Number.isFinite(Date.parse(snapshot.as_of_utc))||Date.parse(snapshot.as_of_utc)>=Date.parse(game.start_utc)){root.append(make('p','Balance pendiente de una captura previa al inicio para este encuentro.'));return root;}
 root.append(make('p','Escenario con tasas históricas por minuto. No cambia la probabilidad de victoria. Captura: '+new Date(snapshot.as_of_utc).toLocaleString('es-CL',{timeZone:'America/Santiago'})));
 for(const team of [game.away,game.home]){
  const s=matches[0].teams[team],box=make('section');box.append(make('h5',team));
  if(s?.status!=='conditional_replacement_scenario'){box.append(make('p','Faltan líneas o historiales completos para calcular el balance.'));root.append(box);continue;}
  box.append(make('p','Minutos históricos de salientes: '+number(s.lost_minutes)+' · Entrantes: '+number(s.incoming_historical_minutes)));
  const table=make('table'),head=make('tr');for(const t of ['Aporte por partido','Salientes','Entrantes','Cambio neto del escenario'])head.append(make('th',t));table.append(head);
  for(const [key,label] of [['goals','Goles'],['assists','Asistencias'],['shots','Tiros'],['penalty_minutes','Min. penalidad']]){const row=make('tr');row.append(make('th',label));for(const value of [s.lost_historical_contribution[key],s.incoming_historical_contribution[key],s.delta[key]])row.append(make('td',number(value)));table.append(row);}
  const scroll=make('div');scroll.className='nhl-table-scroll';scroll.append(table);box.append(scroll);
  const detail=make('details');detail.append(make('summary','Reparto por jugador'));const list=make('ul');
  for(const p of s.players)list.append(make('li',(p.name||p.player_id)+': '+number(p.historical_minutes)+' → '+number(p.scenario_minutes)+' min ('+(p.minutes_delta>=0?'+':'')+number(p.minutes_delta)+')'));detail.append(list);box.append(detail);root.append(box);
 }
 root.append(make('p','Supuestos: entrantes parten de su uso histórico; el saldo se reparte proporcionalmente entre quienes permanecen. Tasas constantes, sin ajuste por rol PP/PK, rival o entrenador. Salir de la proyección no confirma lesión. Menos penalidades no implica automáticamente mejor rendimiento.'));return root;
};scope.PulsoNhlAbsenceExposure=api;
})(window);
