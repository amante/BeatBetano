"use strict";
(async function(){
 const root=document.getElementById("nhl-five-market");
 if(!root || new URLSearchParams(location.search).get("sport")!=="nhl")return;
 const make=(tag,text,cls)=>{
   const x=document.createElement(tag);
   if(text!==undefined)x.textContent=text;
   if(cls)x.className=cls;
   return x;
 };
 const pct=x=>typeof x==="number" && Number.isFinite(x)?(x*100).toFixed(1).replace(".",",")+"%":"—";
 const normalizedGameId=value=>String(value||"").replace(/^nhl[-_:]/,"");
 function renderCalendarProbabilities(data){
  const date=document.getElementById("daily-date")?.value;
  document.querySelectorAll(".daily-match[data-nhl-id]").forEach(row=>{
   row.querySelectorAll(".nba-match-probability,.nhl-calendar-probability").forEach(item=>item.remove());
   if(!data||data.date!==date)return;
   const id=normalizedGameId(row.dataset.nhlId);
   const game=data.games.find(item=>normalizedGameId(item.game_id)===id&&item.status==="experimental_forecast"&&item.ml&&typeof item.ml.home==="number"&&typeof item.ml.away==="number");
   if(!game)return;
   for(const [side,value] of [["away",game.ml.away],["home",game.ml.home]]){
    const team=row.querySelector(".daily-team-"+side);
    if(!team)continue;
    const name=team.querySelector(".daily-team-name")?.textContent||game[side];
    const badge=make("span",Math.round(value*100)+"%","nba-match-probability is-experimental");
    const trend=game.ml_trend&&game.ml_trend[side];
    if(trend==="up"||trend==="down"){
     const arrow=make("span",trend==="up"?"↑":"↓","nhl-probability-trend "+(trend==="up"?"is-up":"is-down"));
     arrow.setAttribute("aria-label",trend==="up"?"La probabilidad subió":"La probabilidad bajó");
     arrow.title=arrow.getAttribute("aria-label");badge.append(arrow);
    }
    badge.setAttribute("aria-label",name+": "+pct(value)+" probabilidad experimental de victoria");
    badge.title="Probabilidad experimental: "+name+" "+pct(value);
    team.append(badge);
   }
  });
 }
 function addDetailPanelContent(panel,card,selectors,emptyText){
  panel.replaceChildren(make("h4",panel.dataset.title));
  let count=0;
  if(card){
   for(const node of card.querySelectorAll(selectors)){
    if(node.classList.contains("nhl-minute-adjusted-ml")&&!node.children.length&&!node.textContent.trim())continue;
    panel.append(node.cloneNode(true));count++;
   }
  }
  if(!count)panel.append(make("p",emptyText,"nba-game-disclosure__empty"));
  return count;
 }
 function integrateCalendarDetails(data){
  const selected=document.getElementById("daily-date")?.value;
  const rows=[...document.querySelectorAll(".daily-match[data-nhl-id]")];
  let attachedForecasts=0;
  const cards=[...root.querySelectorAll(".nhl-forecast-card[data-game-id]")];
  for(const original of rows){
   let disclosure=original.closest("details.nhl-game-disclosure");
   let summary=disclosure?.querySelector(":scope > summary.daily-match");
   if(!disclosure){
    const id=normalizedGameId(original.dataset.nhlId);
    disclosure=make("details",undefined,"nba-game-disclosure nhl-game-disclosure");
    disclosure.dataset.nhlId=id;
    summary=make("summary",undefined,original.className+" nhl-game-summary");
    for(const [key,value] of Object.entries(original.dataset||{}))summary.dataset[key]=value;
    summary.setAttribute("aria-label","Ver pronóstico y detalles de "+original.textContent.trim());
    while(original.firstChild)summary.append(original.firstChild);
    disclosure.append(summary);
    const content=make("div",undefined,"nba-game-disclosure__content");
    const columns=make("div",undefined,"nba-game-disclosure__columns");
    const left=make("section",undefined,"nba-game-disclosure__panel nba-game-disclosure__lineup-panel");
    left.dataset.title="Alineaciones, porteros y bajas";
    const right=make("section",undefined,"nba-game-disclosure__panel nba-game-disclosure__run-panel");
    right.dataset.title="Corrida y probabilidades";
    columns.append(left,right);content.append(columns);disclosure.append(content);
    original.replaceWith(disclosure);
   }
   const id=normalizedGameId(summary?.dataset.nhlId||disclosure.dataset.nhlId);
   const left=disclosure.querySelector(".nba-game-disclosure__lineup-panel");
   const right=disclosure.querySelector(".nba-game-disclosure__run-panel");
   const game=data&&data.date===selected&&Array.isArray(data.games)?data.games.find(item=>normalizedGameId(item.game_id)===id):null;
   const card=game?.status==="experimental_forecast"?cards.find(item=>normalizedGameId(item.dataset.gameId)===id):null;
   if(card)attachedForecasts++;
   addDetailPanelContent(left,card,".nhl-goalie-comparison,.nhl-match-context,.nhl-absence-exposure,.nhl-pregame-input-inventory","No hay una captura disponible de porteros, alineaciones o bajas para este partido.");
   right.replaceChildren(make("h4","Corrida y probabilidades"));
   if(game){
    const runLabel=["Captura "+data.date,data.run_id?"corrida #"+data.run_id:null,"Experimental · sin calibrar"].filter(Boolean).join(" · ");
    right.append(make("p",runLabel,"nba-game-disclosure__run-meta"));
   }else{
    right.append(make("p","No hay pronóstico publicado para la fecha seleccionada. No se muestra una captura de otra fecha.","nba-game-disclosure__run-meta"));
   }
   const rightCount=addDetailPanelContent(right,card,".nhl-market-label,.nhl-ml-grid,.nhl-minute-adjusted-ml,.nhl-forecast-card > .daily-source,.nhl-extra-markets","No hay porcentajes de pronóstico publicados para este partido.");
   if(!rightCount&&game&&game.status!=="experimental_forecast"){
    const status=game.status==="not_pregame_at_capture"?"La captura se realizó después del inicio; no se genera pronóstico pregame.":"No hubo evidencia suficiente para generar un pronóstico.";
    right.append(make("p",status,"nba-game-disclosure__empty"));
   }
   const jointRoot=document.getElementById("nhl-joint-model");
   const jointGame=jointRoot&&[...jointRoot.querySelectorAll(".nhl-joint-game[data-game-id]")].find(item=>normalizedGameId(item.dataset.gameId)===id);
   right.querySelector(".nhl-inline-joint")?.remove();
   if(jointGame){
    const joint=make("details",undefined,"nhl-inline-joint");
    joint.append(make("summary","Escenarios integrados por porteros · experimental"));
    joint.append(jointGame);
    right.append(joint);
   }
  }
  const hasRows=rows.length>0;
  root.hidden=Boolean(hasRows&&cards.length>0&&attachedForecasts===cards.length);
  root.style.display=root.hidden?"none":"";
  const jointRoot=document.getElementById("nhl-joint-model");
  if(jointRoot){
   const remaining=jointRoot.querySelectorAll(".nhl-joint-game").length;
   const blocked=jointRoot.querySelector(".nhl-joint-blocked");
   if(remaining===0&&!blocked&&hasRows&&jointRoot.dataset.publishedDate===selected){jointRoot.hidden=true;jointRoot.style.display="none";}
   else{jointRoot.hidden=false;jointRoot.style.display="";}
  }
 }

  let published=null,loadError=null;
 function renderContent(){
 root.hidden=false;root.style.display="";
 renderCalendarProbabilities(published);
 root.replaceChildren(make("h3","Pronósticos de la jornada"));
 const source=make("p","Cargando captura…","daily-source");
 const meta=make("div",undefined,"nhl-market-meta");
 meta.append(make("span","Experimental","nhl-experimental-badge"),source);root.append(meta);
 const note=make("p","Base histórica experimental; el ganador incorpora descanso solo con calendario pregame verificado. Sin cuotas ni recomendación de apuesta.","nhl-probability-note");
 root.append(note);
 const date=document.getElementById("daily-date").value;
 if(!published){source.textContent=loadError?"No se pudo cargar la publicación: "+loadError:"Cargando captura…";return;}
 const data=published;
 if(date!==data.date){
  source.textContent="Fecha seleccionada: "+date;
  root.append(make("p","Aún no hay pronósticos publicados para esta fecha. Si hay encuentros pendientes, ejecuta la jornada seleccionada.","daily-empty"));
  root.append(make("p","Última captura disponible: "+data.date+". No se muestran probabilidades de otra fecha.","daily-source"));return;
 }
  source.textContent="Captura del "+data.date+" · "+data.experimental_predicted_games+" encuentro"+(data.experimental_predicted_games===1?"":"s")+" con pronóstico";
  const archive=make("details",undefined,"nhl-archive");
  const excluded=data.games.filter(g=>g.status!=="experimental_forecast");
  archive.append(make("summary",excluded.length+" encuentro"+(excluded.length===1?"":"s")+" sin pronóstico pregame"));
  if(!data.games.length){root.append(make("p","Sin partidos programados en la fecha de la captura.","daily-empty"));return;}
  const plus3=window.PulsoNhlPlus3.summarize(data.games);
  const plus3Note=make("p",plus3.count?"Promedio +3 de la jornada: "+pct(plus3.mean)+" · "+plus3.count+" pronósticos de equipos. ↑ Sobre promedio destaca valores estrictamente superiores; no indica valor de apuesta.":"Sin probabilidades +3 para calcular un promedio.","daily-source");
  for(const g of data.games){
   if(g.status!=="experimental_forecast"){
    const row=make("div",undefined,"nhl-archive-row");
    row.append(make("strong",g.away+" — "+g.home),make("span",g.status==="not_pregame_at_capture"?"Ya había comenzado al capturar":"Sin evidencia suficiente"));
    archive.append(row);continue;
   }
   const card=make("section",undefined,"nhl-forecast-card");card.dataset.gameId=String(g.game_id);card.dataset.runId=String(data.run_id||"");
   const heading=make("div",undefined,"nhl-forecast-heading"),identity=make("div");
   identity.append(make("h4",g.away+" — "+g.home),make("p",new Date(g.start_utc).toLocaleString("es-CL",{timeZone:"America/Santiago",dateStyle:"medium",timeStyle:"short"})+" · Chile"));
   const pending=Date.parse(g.start_utc)>Date.now();
   heading.append(identity,make("span",pending?"Por comenzar":"Captura pregame","nhl-upcoming"));card.append(heading);
   const valid=g.ml&&g.rt&&g.first_to_plus3&&typeof g.home_plus3==="number"&&typeof g.away_plus3==="number";
   if(!valid){card.append(make("p","Mercados incompletos: no se muestran probabilidades parciales."));root.append(card);continue;}
   card.append(make("div",g.module_effects?.lineup_availability?.status==="applied_experimental"?"Probabilidad Ganador publicada · ajuste experimental de disponibilidad · incluye desempate":"Probabilidad Ganador publicada · incluye desempate","nhl-market-label"));
   const probabilities=make("div",undefined,"nhl-ml-grid");
   for(const [team,value] of [[g.away,g.ml.away],[g.home,g.ml.home]]){
    const side=make("div",undefined,"nhl-probability");side.append(make("span",team),make("strong",pct(value)));probabilities.append(side);
   }
   card.append(probabilities);
   card.append(window.PulsoNhlMinuteML.create(g));
   card.append(window.PulsoNhlGoalieComparison.create(data,g));
   card.append(window.PulsoNhlContext.create(g));
   card.append(window.PulsoNhlAbsenceExposure.create(g));
   if(window.PulsoNhlInputs)card.append(window.PulsoNhlInputs.create(g));
   const rest=g.module_effects?.rest;
   if(rest){
    let message="Descanso no ajustado: falta evidencia pregame verificada; el porcentaje quedó sin este ajuste.";
    if(rest.status==="applied"){
     const delta=Number(rest.probability_delta_percentage_points);
     const signed=(delta>0?"+":"")+delta.toFixed(2).replace(".",",")+" pp";
     message="Descanso incluido en Ganador: "+g.home+" "+rest.home_rest_days+" días · "+g.away+" "+rest.away_rest_days+" días · cambio "+signed+".";
    }
    card.append(make("p",message,"daily-source"));
   }
   const lineup=g.module_effects?.lineup_availability;
   if(lineup){
    let message="Disponibilidad no aplicada: "+(lineup.reason||"faltan escenarios completos y previos al partido para ambos equipos")+"; se conserva el porcentaje base.";
    if(lineup.status==="applied_experimental"){
     const delta=Number(lineup.probability_delta_home_percentage_points);
     const signed=(delta>0?"+":"")+delta.toFixed(2).replace(".",",")+" pp";
     message="Disponibilidad y reparto de minutos incluidos en Ganador (experimental): "+g.home+" "+pct(lineup.baseline_probability_home)+" → "+pct(lineup.scenario_probability_home)+" · cambio "+signed+" · sin validación predictiva.";
    }
    card.append(make("p",message,"daily-source"));
   }
   const extra=make("details",undefined,"nhl-extra-markets");extra.append(make("summary","Ver los cinco mercados y comparación +3"));
   const rows=[
     ["Ganador ML",pct(g.ml.home),pct(g.ml.away),"—"],
     ["Tiempo regular RT",pct(g.rt.home),pct(g.rt.away),"Empate "+pct(g.rt.draw)],
     ["Logra ventaja de +3",pct(g.home_plus3),pct(g.away_plus3),"Eventos no excluyentes"],
     ["Primero en alcanzar +3",pct(g.first_to_plus3.home),pct(g.first_to_plus3.away),"Ninguno "+pct(g.first_to_plus3.none)]
   ];
   const table=make("table",undefined,"nhl-market-table");
   const head=make("thead"),headRow=make("tr");
   for(const heading of ["Mercado",g.home,g.away,"Otro"])headRow.append(make("th",heading));
   head.append(headRow);table.append(head);
   const body=make("tbody");
   for(const cells of rows){const tr=make("tr");for(const [i,c] of cells.entries())tr.append(make(i===0?"th":"td",c));body.append(tr);}
   table.append(body);
   const plus3row=body.children[2];
   for(const [index,value] of [[1,g.home_plus3],[2,g.away_plus3]]){
    if(window.PulsoNhlPlus3.higher(value,plus3)){
     const cell=plus3row.children[index];
     cell.classList.add("nhl-plus3-above-average");
     cell.append(make("span"," ↑ Sobre promedio","nhl-plus3-label"));
     cell.title="Supera el promedio +3 de la jornada ("+pct(plus3.mean)+")";
    }
   }
   const scroll=make("div",undefined,"nhl-table-scroll");scroll.append(table);extra.append(scroll,plus3Note.cloneNode(true));
   card.append(extra);root.append(card);
  }
  if(!data.experimental_predicted_games)root.append(make("p","No hay pronósticos pregame publicados para esta captura.","daily-empty"));
  if(excluded.length)root.append(archive);
  const publication=make("p",undefined,"nhl-publication-note");const link=make("a","Ver ejecuciones en GitHub");
  link.href="https://github.com/amante/BeatBetano/actions/workflows/pulso-nhl-prospective.yml";link.target="_blank";link.rel="noopener noreferrer";
  publication.append(link);root.append(publication);

 }
 function render(){renderContent();integrateCalendarDetails(published);}
 document.addEventListener("pulso:date-change",render);
 document.addEventListener("pulso:nhl-joint-rendered",()=>integrateCalendarDetails(published));
 window.PulsoNhlContext.ready.then(render);
 window.PulsoNhlMinuteML.ready.then(render);
 window.PulsoNhlAbsenceExposure.ready.then(render);
 window.PulsoNhlGoalieComparison.ready.then(render);
 if(window.PulsoNhlInputs)window.PulsoNhlInputs.ready.then(render);
 render();
 try{
  const response=await fetch("./data/nhl-daily-predictions-latest.json",{cache:"no-store"});
  if(!response.ok)throw new Error("HTTP "+response.status);
  const data=await response.json();
  if(data.kind!=="nhl_research_daily_presentation_275" || data.official!==false ||
     data.odds_used!==false || !Array.isArray(data.games) ||
     data.official_schedule_games!==data.games.length ||
     data.games.some(g=>!g.game_id||!g.home||!g.away||!g.start_utc))throw new Error("Reporte no verificado");
  published=data;
 }catch(e){loadError=e.message;}
 render();
})();
