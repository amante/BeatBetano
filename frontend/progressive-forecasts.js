"use strict";
(function(){
 const sports=["nba","nfl","nhl","soccer","tennis"],stages={initial:"Inicial",update:"Actualización",final_pregame:"Última pregame"};
 const date=x=>typeof x==="string"&&Number.isFinite(Date.parse(x));
 function validRevision(r,sport){
  const keys=sport==="soccer"?["home","draw","away"]:["home","away"];
  return r&&Number.isInteger(r.revision)&&r.revision>0&&Object.hasOwn(stages,r.stage)&&date(r.emitted_at_utc)&&date(r.cutoff_utc)&&date(r.start_utc)&&
   Date.parse(r.cutoff_utc)<=Date.parse(r.emitted_at_utc)&&Date.parse(r.emitted_at_utc)<Date.parse(r.start_utc)&&
   typeof r.model_version==="string"&&r.model_version.trim()&&typeof r.snapshot_sha256==="string"&&/^[a-f0-9]{64}$/.test(r.snapshot_sha256)&&r.calibration_certified===false&&r.selection_status==="PASS"&&
   Array.isArray(r.assumptions)&&r.assumptions.every(x=>typeof x==="string")&&Array.isArray(r.unresolved_inputs)&&r.unresolved_inputs.every(x=>typeof x==="string")&&
   r.probabilities&&Object.keys(r.probabilities).length===keys.length&&keys.every(k=>typeof r.probabilities[k]==="number"&&Number.isFinite(r.probabilities[k])&&r.probabilities[k]>0&&r.probabilities[k]<1)&&
   Math.abs(keys.reduce((n,k)=>n+r.probabilities[k],0)-1)<1e-6;
 }
 function validate(data){
  if(!data||data.kind!=="progressive_forecast_index"||!Array.isArray(data.events)||!Array.isArray(data.errors)||!date(data.generated_at_utc)||data.errors.some(e=>!e||typeof e.sport!=="string"))return false;
  const seen=new Set();
  for(const e of data.events){
   const key=e.sport+":"+e.event_id;
   if(!sports.includes(e.sport)||typeof e.event_id!=="string"||seen.has(key)||!date(e.start_utc)||!Array.isArray(e.participants)||e.participants.length!==2||e.participants.some(x=>typeof x!=="string"||!x)||e.participants[0]===e.participants[1])return false;
   seen.add(key);
   if(!Array.isArray(e.history)||!e.history.length||e.history.some((r,i)=>!validRevision(r,e.sport)||r.revision!==i+1||(i&&Date.parse(r.cutoff_utc)<=Date.parse(e.history[i-1].cutoff_utc))))return false;
   if(JSON.stringify(e.initial)!==JSON.stringify(e.history[0])||JSON.stringify(e.latest)!==JSON.stringify(e.history[e.history.length-1])||e.start_utc!==e.latest.start_utc)return false;
   if(!e.delta||Object.keys(e.delta).length!==Object.keys(e.initial.probabilities).length)return false;
   for(const k of Object.keys(e.initial.probabilities))if(typeof e.delta[k]!=="number"||!Number.isFinite(e.delta[k])||Math.abs(e.delta[k]-(e.latest.probabilities[k]-e.initial.probabilities[k]))>1e-10)return false;
  }
  return true;
 }
 const day=x=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(x));
 const forDay=(data,sport,value)=>data.events.filter(e=>e.sport===sport&&day(e.start_utc)===value);
 if(typeof module!=="undefined")module.exports={validate,forDay};
 if(typeof window==="undefined"||typeof document==="undefined")return;
 const sport=new URLSearchParams(location.search).get("sport");if(!sports.includes(sport))return;
 const root=document.getElementById("progressive-forecasts");if(!root)return;
 const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 const local=x=>new Date(x).toLocaleString("es-CL",{timeZone:"America/Santiago",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"});
 const pct=x=>(100*x).toLocaleString("es-CL",{minimumFractionDigits:1,maximumFractionDigits:1})+" %";
 const change=x=>x===0?"Sin cambio":(x>0?"+":"−")+(100*Math.abs(x)<.05?"<0,1":(100*Math.abs(x)).toLocaleString("es-CL",{minimumFractionDigits:1,maximumFractionDigits:1}))+" p.p.";
 const textMap={
  "Current lineup and availability not verified by this adapter":"Alineación y disponibilidad aún sin verificar.",
  "Existing source-model forecast; availability has not been independently audited by this adapter.":"Base del modelo disponible; alineación y disponibilidad todavía pendientes de verificar.",
  "Existing Premier League season-frozen Poisson model; no current lineup adjustment.":"Base histórica de Premier League, sin ajuste de la alineación actual.",
  "Confirmed lineup and current availability":"Alineación confirmada y disponibilidad actual."
 };
 let data=null,error="",lineupScenarioData=null;
 function render(){
  root.replaceChildren();
  const header=el("div",undefined,"forecast-heading"),heading=el("div");heading.append(el("div","PRONÓSTICOS · EVOLUCIÓN PREGAME","eyebrow"),el("h2","Predicciones y actualizaciones"));header.append(heading);
  const legacy=document.getElementById("daily-date"),picker=el("input"),label=el("label","Fecha de pronósticos","forecast-date");picker.type="date";picker.value=legacy?.value||day(new Date().toISOString());picker.setAttribute("aria-label","Fecha de pronósticos");
  picker.addEventListener("change",()=>{if(!/^20\d{2}-\d{2}-\d{2}$/.test(picker.value))return;if(legacy){legacy.value=picker.value;legacy.dispatchEvent(new Event("change",{bubbles:true}));}});label.append(picker);header.append(label);root.append(header);
  root.append(el("p","La primera base y sus revisiones, sin esperar alineaciones confirmadas.","forecast-intro"));
  if(error){root.append(el("p","No se pudieron cargar las predicciones. Intenta actualizar la página.","forecast-empty"));return;}
  if(!data){root.append(el("p","Cargando predicciones…","forecast-empty"));return;}
  const selected=document.getElementById("daily-date")?.value||day(new Date().toISOString()),rows=forDay(data,sport,selected);
  const relevant=data.errors.filter(e=>e.sport===sport);
  root.append(el("p",selected+" · "+rows.length+" partido"+(rows.length===1?"":"s")+" con pronóstico archivado · Hora de Chile","forecast-meta"));
  if(relevant.length)root.append(el("p",relevant.length+" registro(s) requieren revisión; sus porcentajes no se muestran.","forecast-notice"));
  if(!rows.length){root.append(el("p",sport==="tennis"?"Todavía no hay un modelo numérico de tenis conectado.":"No hay pronósticos archivados para este deporte y fecha. Esto no significa que no haya partidos.","forecast-empty"));return;}
  const grid=el("div",undefined,"forecast-grid");
  for(const e of rows){
   const first=e.initial,last=e.latest,card=el("article",undefined,"forecast-card");
   const lineupScenario=sport==="nhl"?(lineupScenarioData?.games||[]).find(g=>String(g.game_id)===String(e.event_id)&&Date.parse(g.start_utc)===Date.parse(e.start_utc)):null;
   const keys=Object.keys(last.probabilities),previous=e.history.length>1?e.history[e.history.length-2]:null;
   const noProbabilityChange=previous&&keys.every(key=>pct(previous.probabilities[key])===pct(last.probabilities[key]));
   const top=el("div",undefined,"forecast-card-top");top.append(el("span",noProbabilityChange?"Actualización · sin cambio":stages[last.stage],"forecast-badge"),el("span",Date.now()>=Date.parse(e.start_utc)?"Historial pregame · partido iniciado":last.source_classification==="illustrative"?"Ejemplo ilustrativo":last.calibration_certified?"Calibración certificada":"Sin calibración certificada","forecast-state"));card.append(top);
   card.append(el("h3",e.participants[1]+" — "+e.participants[0]),el("p",local(e.start_utc)+" · "+(sport==="soccer"?"Resultado en 90 minutos":"Ganador"),"forecast-meta"));
   card.append(el("p","Inicial: "+local(first.emitted_at_utc)+" · Última: "+local(last.emitted_at_utc),"forecast-meta"));
   if(Date.now()<Date.parse(e.start_utc)&&Date.now()-Date.parse(last.emitted_at_utc)>8*3600000)card.append(el("p","Sin actualización en las últimas 8 horas.","forecast-notice"));
   const table=el("table",undefined,"forecast-table"),head=el("thead"),hr=el("tr");for(const t of ["Resultado","Inicial","Última","Cambio"])hr.append(el("th",t));head.append(hr);table.append(head);const body=el("tbody");
   for(const key of (sport==="soccer"?["home","draw","away"]:["home","away"])){
    const tr=el("tr");tr.append(el("th",key==="draw"?"Empate":e.participants[key==="home"?0:1]),el("td",pct(first.probabilities[key])),el("td",pct(last.probabilities[key])),el("td",change(e.delta[key])));body.append(tr);
   }table.append(body);card.append(table);
   const scenarioAwayBaseline=Number.isFinite(lineupScenario?.baseline_ml_away)
    ?lineupScenario.baseline_ml_away
    :Number.isFinite(lineupScenario?.baseline_ml_home)?1-lineupScenario.baseline_ml_home:NaN;
   if(lineupScenario?.status==="experimental_minute_scenario"&&
      Number.isFinite(lineupScenario.baseline_ml_home)&&Number.isFinite(lineupScenario.scenario_ml_home)&&
      Number.isFinite(scenarioAwayBaseline)&&Number.isFinite(lineupScenario.scenario_ml_away)){
    const panel=el("section",undefined,"nhl-lineup-scenario");
    panel.append(el("h4","Disponibilidad y minutos · escenario experimental"));
    panel.append(el("p","Esta simulación es independiente del historial de arriba; no lo reemplaza.","forecast-meta"));
    panel.append(el("p",e.participants[0]+" (local): "+pct(lineupScenario.baseline_ml_home)+" → "+pct(lineupScenario.scenario_ml_home)));
    panel.append(el("p",e.participants[1]+" (visita): "+pct(scenarioAwayBaseline)+" → "+pct(lineupScenario.scenario_ml_away)));
    const delta=Number(lineupScenario.delta_home_pp);
    panel.append(el("p","Cambio local: "+(delta>0?"+":"")+delta.toLocaleString("es-CL",{minimumFractionDigits:2,maximumFractionDigits:2})+" p.p. · corte "+local(lineupScenarioData.as_of_utc),"forecast-notice"));
    panel.append(el("p","Sin validación predictiva; usa tasas históricas por minuto y Poisson independiente.","forecast-meta"));
    card.append(panel);
   }else if(lineupScenario?.status==="blocked"){
    const pending=el("details",undefined,"nhl-lineup-scenario-pending");
    pending.append(el("summary","Escenario experimental de disponibilidad no calculado"));
    pending.append(el("p",lineupScenario.reason||"Falta evidencia completa para ambos equipos."));
    card.append(pending);
   }
   if(first.model_version!==last.model_version)card.append(el("p","La versión del modelo cambió entre estas corridas.","forecast-notice"));
   const info=el("details"),summary=el("summary","Supuestos e información pendiente");info.append(summary);
   info.append(el("p","Supuestos","forecast-detail-label"));for(const value of last.assumptions)info.append(el("p",textMap[value]||value));
   info.append(el("p","Pendiente","forecast-detail-label"));if(!last.unresolved_inputs.length)info.append(el("p","No se declararon pendientes en esta corrida."));for(const value of last.unresolved_inputs)info.append(el("p",textMap[value]||value));
   info.append(el("p","Versión: "+last.model_version),el("p","Campo de probabilidad: "+(last.source_probability_field||"no declarado")),el("p","Corte de datos: "+local(last.cutoff_utc)));card.append(info);
   const history=el("details");history.append(el("summary","Ver "+e.history.length+" corridas"));
   for(const [index,r] of e.history.entries()){
    const prior=index?e.history[index-1]:null;
    const unchanged=prior&&Object.keys(r.probabilities).every(key=>pct(prior.probabilities[key])===pct(r.probabilities[key]));
    const state=index===0?"Inicial":unchanged?"Sin cambio de probabilidad":"Probabilidad modificada";
    history.append(el("p","#"+r.revision+" · "+stages[r.stage]+" · "+local(r.emitted_at_utc)+" · "+state+" · Modelo: "+r.model_version+" · "+Object.entries(r.probabilities).map(([k,v])=>(k==="draw"?"Empate":e.participants[k==="home"?0:1])+" "+pct(v)).join(" / ")));
   }card.append(history);
   card.append(el("p",last.calibration_certified?"Calibración certificada.":"Estado experimental · calibración no certificada y sin evaluación de rendimiento.","forecast-footnote"));grid.append(card);
  }root.append(grid);
 }
 const ready=(async()=>{render();try{const response=await fetch("./data/forecast-index.json",{cache:"no-store"});if(!response.ok)throw Error("Missing forecast index");const payload=await response.json();if(!validate(payload))throw Error("Invalid forecast index");data=payload;}catch(e){error=e.message;}
  if(sport==="nhl")try{const response=await fetch("./data/nhl-minute-adjusted-ml.json",{cache:"no-store"});if(response.ok){const scenario=await response.json();if(scenario.kind==="nhl_minute_adjusted_ml_v1"&&Array.isArray(scenario.games)&&date(scenario.as_of_utc))lineupScenarioData=scenario;}}catch{}
  render();})();
 document.getElementById("daily-date")?.addEventListener("change",render);
 window.PulsoProgressiveForecasts={ready,render};
})();
