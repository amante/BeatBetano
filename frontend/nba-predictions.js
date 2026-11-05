"use strict";
(function(){
 const stamp=x=>typeof x==="string"&&Number.isFinite(Date.parse(x));
 function validate(x){
  if(!x||x.kind!=="nba_forward_publication_v2"||!stamp(x.as_of_utc)||!Array.isArray(x.games)||x.performance_metrics!==null||x.sporting_adjustment_applied!==false||!stamp(x.last_source_capture_utc)||!Array.isArray(x.sporting_evidence_errors)||!x.calendar_date_coverage_chile)return false;
  const ids=new Set();
  for(const g of x.games){
   if(!g.game_id||ids.has(g.game_id)||!stamp(g.tipoff_utc)||!g.home_team||!g.away_team||g.home_team===g.away_team||typeof g.status!=="string"||!Array.isArray(g.issues)||!g.sporting)return false;
   for(const team of [g.home_team,g.away_team]){const s=g.sporting[team];if(s&&(!stamp(s.observed_at_utc)||Date.parse(s.observed_at_utc)>=Date.parse(g.tipoff_utc)||!Array.isArray(s.players)||!Array.isArray(s.provider_starters)))return false;}
   if(g.outcome&&(!Number.isInteger(g.outcome.home_points)||!Number.isInteger(g.outcome.away_points)||!stamp(g.outcome.result_observed_at_utc)))return false;
   ids.add(g.game_id);const p=g.first_prediction;
   if(p&&(p.game_id!==g.game_id||(!g.issues.length&&(p.home_team!==g.home_team||p.away_team!==g.away_team))||!stamp(p.prediction_as_of_utc)||Date.parse(p.prediction_as_of_utc)>=Date.parse(p.tipoff_utc)||[p.elo_p_home,p.challenger_p_home].some(v=>!Number.isFinite(v)||v<=0||v>=1)))return false;
  }
  return true;
 }
 const day=x=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(x));
 const forDay=(x,d)=>x.games.filter(g=>day(g.tipoff_utc)===d);
 const stale=(x,now=Date.now())=>!stamp(x.last_source_capture_utc)||now-Date.parse(x.last_source_capture_utc)>8*3600*1000;
 if(typeof module!=="undefined")module.exports={validate,forDay,stale};
 if(typeof window==="undefined"||typeof document==="undefined")return;
 if(new URLSearchParams(location.search).get("sport")!=="nba")return;
 const root=document.createElement("section");root.className="panel";
 const agenda=document.getElementById("daily-results");
 if(agenda)agenda.replaceChildren(root);else document.querySelector("main").prepend(root);
 for(const selector of ["#daily-stats",".daily-yesterday",".simulation-panel","#nhl-five-market","#nhl-joint-model","#pulso-nhl-research"]){
  const panel=document.querySelector(selector);if(panel){panel.hidden=true;panel.style.display="none";}
 }
 const el=(tag,text)=>{const x=document.createElement(tag);x.textContent=text;return x;};
 const local=x=>new Date(x).toLocaleString("es-CL",{timeZone:"America/Santiago"});
 let data=null,error="";
 function render(){
  root.replaceChildren(el("h2","Pronósticos NBA"));
  if(!data){
   const label=document.getElementById("daily-label"),source=document.getElementById("feed-message");
   if(label)label.textContent="NBA · Registro prospectivo";
   if(source)source.textContent=error||"Cargando el registro NBA…";
   root.append(el("p",error||"Cargando el registro NBA…"));return;
  }
  const selected=document.getElementById("daily-date").value,rows=forDay(data,selected);
  const label=document.getElementById("daily-label"),source=document.getElementById("feed-message");
  if(label)label.textContent="NBA · "+selected+" · "+rows.length+" partido"+(rows.length===1?" registrado":"s registrados");
  if(source)source.textContent="Calendario y emisiones del registro NBA · captura "+local(data.last_source_capture_utc)+" · fecha Chile.";
  root.append(el("p","Elo y Challenger experimentales · sin ajustes de lesiones ni alineaciones · Knicks excluido."));
  root.append(el("p","Última captura: "+local(data.last_source_capture_utc)+(stale(data)?" · Datos desactualizados; revisar la fuente.":"")));
  if(data.source_error_count)root.append(el("p","El registro conserva fallos de fuente. La cobertura requiere revisión."));
  if(data.sporting_evidence_errors.length)root.append(el("p","Hay evidencia deportiva que no pudo verificarse."));
  if(!rows.length)root.append(el("p",data.calendar_date_coverage_chile[selected]?"La fuente no reporta partidos dentro de esta cohorte para la fecha elegida.":"La fecha elegida todavía no tiene cobertura suficiente."));
  for(const g of rows){
   const card=el("article","");card.append(el("h3",g.away_team+" — "+g.home_team));
   const state=g.outcome?"Final":g.source_state==="in"?"En juego al último corte":g.source_status==="STATUS_FINAL"?"Final · cierre emparejado pendiente":g.source_status==="STATUS_POSTPONED"?"Aplazado":g.source_status==="STATUS_CANCELED"?"Cancelado":g.status.includes("review")?"Requiere revisión":Date.now()>=Date.parse(g.tipoff_utc)?"Sin actualización posterior al inicio":"Por comenzar";
   card.append(el("p",local(g.tipoff_utc)+" · "+state));
   const p=g.first_prediction;
   if(p&&!g.issues.length){
    card.append(el("p","Emisión pregame original: "+local(p.prediction_as_of_utc)));
    for(const [name,key] of [["Elo","elo_p_home"],["Challenger","challenger_p_home"]])card.append(el("p",name+": "+g.away_team+" "+((1-p[key])*100).toFixed(1)+"% · "+g.home_team+" "+(p[key]*100).toFixed(1)+"%"));
   }else card.append(el("p",g.issues.length?"PASS · La emisión original requiere revisión por cambios de la ficha.":"PASS · No hay una pareja de pronósticos pregame válida."));
   if(g.issues.length)card.append(el("p","El partido presenta cambios o conflictos de fuente; requiere revisión."));
   if(g.outcome)card.append(el("p","Marcador final: "+g.away_team+" "+g.outcome.away_points+" — "+g.home_team+" "+g.outcome.home_points));
   for(const team of [g.away_team,g.home_team]){
    const s=g.sporting[team];
    if(!s){card.append(el("p",team+": disponibilidad pregame sin cobertura."));continue;}
    const details=el("details","");details.append(el("summary",team+" · Disponibilidad observada "+local(s.observed_at_utc)));
    details.append(el("p","Fuente suplementaria. No confirma la lista completa de activos ni modifica los porcentajes."));
    details.append(el("p","Quinteto del proveedor ("+(s.lineup_status==="confirmed"?"confirmado por proveedor":s.lineup_status==="projected"?"proyectado":"sin confirmar")+"): "+(s.provider_starters.join(", ")||"sin cobertura")));
    const list=el("ul","");const labels={out:"Fuera según fuente",questionable:"Incierto",available:"Disponible según fuente",unknown:"Sin estado explícito"};
    for(const player of s.players)list.append(el("li",player.player+": "+(labels[player.status]||"Sin resolver")));
    details.append(list);card.append(details);
   }
   card.append(el("p","Modelo deportivo integrado y ventaja +20: PASS. "+(data.evaluation_status==="window_open_metrics_withheld"?"Validación prospectiva en curso.":"Ventana cerrada; falta la auditoría final.")));root.append(card);
  }
 }
 document.getElementById("daily-date").addEventListener("change",render);render();
 window.PulsoNbaForward={ready:(async()=>{try{
  const response=await fetch("./data/nba-forward-latest.json",{cache:"no-store"});
  if(!response.ok)throw Error("source");const x=await response.json();if(!validate(x))throw Error("contract");data=x;
 }catch{error="No se pudo cargar un registro NBA válido. No se muestran porcentajes de otra emisión.";}render();})()};
})();
