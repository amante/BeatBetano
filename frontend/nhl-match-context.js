(function(scope){
 'use strict';
 function select(snapshot,game){
  if(snapshot?.kind!=='nhl_match_context_v1'||!Number.isFinite(Date.parse(snapshot.as_of_utc))||!Array.isArray(snapshot.games))return null;
  const rows=snapshot.games.filter(r=>String(r.game_id)===String(game.game_id)&&r.home===game.home&&r.away===game.away&&r.start_utc===game.start_utc);
  if(rows.length!==1||Date.parse(snapshot.as_of_utc)>=Date.parse(game.start_utc))return null;
  return rows[0];
 }
 const api={select};
 if(typeof module!=='undefined')module.exports=api;
 if(typeof document==='undefined')return;
 let snapshot=null;
 api.ready=fetch('./data/nhl-match-context.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(data=>{snapshot=data;}).catch(()=>{});
 const make=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
 const time=value=>new Date(value).toLocaleString('es-CL',{timeZone:'America/Santiago',dateStyle:'short',timeStyle:'short'});
 api.create=game=>{
  const root=make('section',undefined,'nhl-match-context'),data=select(snapshot,game);
  root.append(make('p',data?['Recinto: '+(data.venue||'Por informar'),data.city].filter(Boolean).join(' · '):'Recinto: pendiente de actualización','nhl-context-venue'));
  if(!data){root.append(make('p','Alineaciones, arqueros, lesionados y árbitros: sin captura pregame verificada para este encuentro.','daily-source'));return root;}
  root.append(make('p','Ficha actualizada: '+time(snapshot.as_of_utc)+' · Chile'+(Date.now()-Date.parse(snapshot.as_of_utc)>90*60000?' · Puede haber cambios posteriores':''),'daily-source'));
  const summary=make('div',undefined,'nhl-context-summary');
  for(const team of [game.away,game.home]){
   const t=data.teams?.[team],box=make('div');
   box.append(make('strong',team),make('p','Arquero titular: sin confirmar'));
   box.append(make('p',t?.goalies?.length?'Arqueros publicados: '+t.goalies.join(' / '):'Arqueros: por informar'));
   box.append(make('p',t?.injuries===null||!t?'Lesionados: por informar':t.injuries.length?'Lesionados reportados: '+t.injuries.join(', '):'Lesionados: ninguno reportado por la fuente'));
   summary.append(box);
  }
  root.append(summary);
  const detail=make('details',undefined,'nhl-context-lines');detail.append(make('summary','Ver líneas de ataque, defensa y árbitros'));
  const grid=make('div',undefined,'nhl-context-summary');
  for(const team of [game.away,game.home]){
   const t=data.teams?.[team],box=make('section');box.append(make('h5',team+' · Alineación proyectada'));
   for(const [key,label] of [['forwards','Ataque'],['defense','Defensa']]){
    box.append(make('h6',label));
    if(!t?.[key]?.length)box.append(make('p','Por informar'));
    else{const list=make('ol');for(const names of t[key])list.append(make('li',names.join(' · ')));box.append(list);}
   }
   box.append(make('p',t?.scratches===null||!t?'Descartados: por informar':t.scratches.length?'Descartados reportados: '+t.scratches.join(', '):'Sin descartados reportados'));
   grid.append(box);
  }
  detail.append(grid,make('p','Árbitros: '+(data.referees?.join(' / ')||'Por informar')),make('p','Jueces de línea: '+(data.linesmen?.join(' / ')||'Por informar')));
  detail.append(make('p','La alineación es proyectada. El orden de los arqueros no confirma al titular. Esta ficha aporta contexto actualizado; las probabilidades publicadas siguen usando el modelo histórico.','daily-source'));
  for(const source of data.sources||[]){
   if(!/^https:\/\/(api-web\.nhle\.com|www\.nhl\.com)\//.test(source.url))continue;
   const link=make('a',source.url.includes('/news/')?'Fuente de alineaciones: NHL.com':'Fuente oficial del encuentro');link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';detail.append(link,make('br'));
  }
  root.append(detail);return root;
 };
 scope.PulsoNhlContext=api;
})(typeof window==='undefined'?globalThis:window);
