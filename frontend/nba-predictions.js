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
 const day=x=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/New_York",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(x));
 const forDay=(x,d)=>x.games.filter(g=>day(g.tipoff_utc)===d);
 function calendarGames(publication,schedule,date){
  const rows=forDay(publication,date).map(game=>({...game,calendar_only:false}));
  const ids=new Set(rows.map(game=>String(game.game_id)));
  for(const fixture of schedule?.games||[]){
   if(fixture?.sport!=="nba"||fixture.id==null||!fixture.start_utc||!fixture.home||!fixture.away||day(fixture.start_utc)!==date)continue;
   const id=String(fixture.id);if(ids.has(id))continue;
   const home=fixture.home,away=fixture.away;
   const hasScore=fixture.completed&&Number.isFinite(Number(fixture.home_score))&&Number.isFinite(Number(fixture.away_score));
   rows.push({game_id:id,home_team:home,away_team:away,tipoff_utc:fixture.start_utc,status:"calendar_only",source_status:fixture.status||"STATUS_SCHEDULED",source_state:"calendar",issues:[],sporting:{[home]:null,[away]:null},first_prediction:null,outcome:hasScore?{home_points:Number(fixture.home_score),away_points:Number(fixture.away_score)}:null,calendar_only:true});
   ids.add(id);
  }
  return rows.sort((a,b)=>a.tipoff_utc.localeCompare(b.tipoff_utc));
 }
 const stale=(x,now=Date.now())=>!stamp(x.last_source_capture_utc)||now-Date.parse(x.last_source_capture_utc)>8*3600*1000;
 if(typeof module!=="undefined")module.exports={validate,forDay,calendarGames,stale};
 if(typeof window==="undefined"||typeof document==="undefined")return;
 if(new URLSearchParams(location.search).get("sport")!=="nba")return;
 const marketPill=document.querySelector(".top-actions .pill");if(marketPill)marketPill.textContent="MERCADO SOLO INFO";
 window.PulsoNbaMatchExpansion=true;
 const root=document.getElementById("nba-results")||document.createElement("section");root.className="panel nba-results-panel";root.hidden=false;
 const agenda=document.getElementById("daily-results");
 if(!root.isConnected){const runner=document.getElementById("nba-runner");if(runner)runner.after(root);else document.querySelector("main").prepend(root);}
 for(const selector of ["#daily-stats",".daily-yesterday",".simulation-panel","#nhl-five-market","#nhl-joint-model","#pulso-nhl-research"]){
  const panel=document.querySelector(selector);if(panel){panel.hidden=true;panel.style.display="none";}
 }
 const el=(tag,text)=>{const x=document.createElement(tag);x.textContent=text;return x;};
 const local=x=>new Date(x).toLocaleString("es-CL",{timeZone:"America/Santiago"});
 const teamNames={ATL:"Atlanta Hawks",BOS:"Boston Celtics",BKN:"Brooklyn Nets",CHA:"Charlotte Hornets",CHI:"Chicago Bulls",CLE:"Cleveland Cavaliers",DAL:"Dallas Mavericks",DEN:"Denver Nuggets",DET:"Detroit Pistons",GS:"Golden State Warriors",GSW:"Golden State Warriors",HOU:"Houston Rockets",IND:"Indiana Pacers",LAC:"LA Clippers",LAL:"Los Angeles Lakers",MEM:"Memphis Grizzlies",MIA:"Miami Heat",MIL:"Milwaukee Bucks",MIN:"Minnesota Timberwolves",NO:"New Orleans Pelicans",NOP:"New Orleans Pelicans",NY:"New York Knicks",NYK:"New York Knicks",OKC:"Oklahoma City Thunder",ORL:"Orlando Magic",PHI:"Philadelphia 76ers",PHX:"Phoenix Suns",POR:"Portland Trail Blazers",SA:"San Antonio Spurs",SAS:"San Antonio Spurs",SAC:"Sacramento Kings",TOR:"Toronto Raptors",UTA:"Utah Jazz",UTAH:"Utah Jazz",WAS:"Washington Wizards",WSH:"Washington Wizards"};
 const teamName=code=>teamNames[code]||code;
 const validMarket=(m,tip)=>m&&m.source_provider==="rotowire"&&m.display_only===true&&m.model_input===false&&stamp(m.observed_at_utc)&&Date.parse(m.observed_at_utc)<Date.parse(tip);
 const marketModelSide=(game,modelHome=null)=>{
  const probabilities=game.first_prediction||game;
  return modelHome!==null&&Number.isFinite(modelHome)?modelHome>.5?"home":modelHome<.5?"away":null:
   probabilities.elo_p_home>.5&&probabilities.challenger_p_home>.5?"home":probabilities.elo_p_home<.5&&probabilities.challenger_p_home<.5?"away":null;
 };
 const goldenMlDiverges=(game,m,modelHome=null)=>{
  const ml=m?.moneyline;if(!validMarket(m,game.tipoff_utc)||!ml||![game.home_team,game.away_team].includes(ml.team)||!Number.isFinite(ml.american_odds)||ml.american_odds===0)return false;
  const favorite=ml.american_odds<0?ml.team:(ml.team===game.home_team?game.away_team:game.home_team);
  const marketSide=favorite===game.home_team?"home":"away",modelSide=marketModelSide(game,modelHome);
  return Boolean(modelSide&&modelSide!==marketSide);
 };
 const marketCalendarStrip=(game,m,modelHome=null)=>{
  const strip=el("div","");strip.className="nba-calendar-market";
  const label=el("span","Mercado");label.className="nba-calendar-market__label";strip.append(label);
  if(!validMarket(m,game.tipoff_utc)){strip.append(el("span","Cuotas RotoWire aún no disponibles"));return strip;}
  const ml=m.moneyline;
  if(ml&&[game.home_team,game.away_team].includes(ml.team)&&Number.isFinite(ml.american_odds)&&ml.american_odds!==0){
   const favorite=ml.american_odds<0?ml.team:(ml.team===game.home_team?game.away_team:game.home_team);
   strip.append(el("span","ML · "+teamName(ml.team)+" "+(ml.american_odds>0?"+":"")+ml.american_odds+" · favorito "+teamName(favorite)));
  }else strip.append(el("span","ML · sin dato"));
  const spread=m.spread;
  if(spread&&[game.home_team,game.away_team].includes(spread.team)&&Number.isFinite(spread.points))strip.append(el("span","Spread · "+teamName(spread.team)+" "+(spread.points>0?"+":"")+spread.points.toFixed(1)));
  else strip.append(el("span","Spread · sin dato"));
  if(Number.isFinite(m.total_points))strip.append(el("span","Total · "+m.total_points.toFixed(1)));
  else strip.append(el("span","Total · sin dato"));
  if(goldenMlDiverges(game,m,modelHome)){const tag=el("span","🎟 GOLDEN TICKET · ML divergente");tag.className="nba-calendar-market__golden";strip.append(tag);}
  strip.append(el("span","RotoWire · "+local(m.observed_at_utc)));return strip;
 };
 const marketPanel=(game,modelHome=null,score=game.point_projection)=>{
  const m=game.market_context;if(!validMarket(m,game.tipoff_utc))return null;
  const lines=[],tags=[];
  const scoreCanSignal=Boolean(score&&score.calibrated===true&&score.experimental!==true);
  const modelSide=marketModelSide(game,modelHome);
  const ml=m.moneyline;
  if(ml&&[game.home_team,game.away_team].includes(ml.team)&&Number.isFinite(ml.american_odds)&&ml.american_odds!==0){
   const favorite=ml.american_odds<0?ml.team:(ml.team===game.home_team?game.away_team:game.home_team);
   lines.push("ML: mercado favorece a "+teamName(favorite)+" · "+teamName(ml.team)+" "+(ml.american_odds>0?"+":"")+ml.american_odds);
   if(goldenMlDiverges(game,m,modelHome))tags.push("GOLDEN TICKET · ML");
  }else lines.push("ML: sin dato");
  if(m.spread&&[game.home_team,game.away_team].includes(m.spread.team)&&Number.isFinite(m.spread.points)){
   lines.push("Spread: "+teamName(m.spread.team)+" "+(m.spread.points>0?"+":"")+m.spread.points.toFixed(1));
   if(score&&Number.isFinite(score.home_points)&&Number.isFinite(score.away_points)){
    const margin=m.spread.team===game.home_team?score.home_points-score.away_points:score.away_points-score.home_points;
    if(scoreCanSignal&&margin+m.spread.points<0)tags.push("GOLDEN TICKET · SPREAD");
   }
  }else lines.push("Spread: sin dato");
  if(Number.isFinite(m.total_points)){
   lines.push("Total O/U: "+m.total_points.toFixed(1));
   if(score&&Number.isFinite(score.home_points)&&Number.isFinite(score.away_points)){
    const projected=score.home_points+score.away_points,diff=projected-m.total_points;
    lines.push("Puntos proyectados: "+projected.toFixed(1)+" · "+(diff>0?"sobre":"bajo")+" la línea por "+Math.abs(diff).toFixed(1));
    if(scoreCanSignal&&diff!==0)tags.push("GOLDEN TICKET · "+(diff>0?"OVER":"UNDER"));
   }
  }else lines.push("Total O/U: sin dato");
  if(!score)lines.push("La proyección exploratoria de puntos aún no está disponible; no se genera señal de Spread ni Total.");
  else if(!scoreCanSignal)lines.push("Puntos exploratorios, sin calibración; se muestran como referencia y no generan GOLDEN TICKET para Spread ni Total.");
  else lines.push("Proyección calibrada disponible para comparación informativa; no altera los porcentajes del modelo.");
  lines.push((Array.isArray(m.referees)&&m.referees.length?"Árbitros: "+m.referees.join(", "):"Árbitros: sin informar"),"RotoWire · captura "+local(m.observed_at_utc));
  const details=el("details","");details.className="nba-market-context";
  details.append(el("summary",tags.length?"Mercado informativo · "+tags.join(" · "):"Mercado informativo · ML / Spread / Total"));
  if(tags.length)details.append(el("p",tags.join(" · "),"nba-golden-tags"));
  for(const line of lines)details.append(el("p",line));
  details.append(el("p","GOLDEN TICKET es solo una etiqueta informativa; no es una predicción ni recomendación y no altera las probabilidades."));
  return details;
 };
 const normalize=value=>Array.from(String(value||"").normalize("NFD")).filter(ch=>ch.codePointAt(0)<768||ch.codePointAt(0)>879).join("").toLowerCase().replaceAll(".","").trim().split(" ").filter(Boolean).join(" ");
 const rosterPlayer=(raw,players)=>{
  const key=normalize(raw),exact=players.find(p=>normalize(p.player)===key);if(exact)return exact;
  const parts=key.split(" ");if(parts.length<2||parts[0].length!==1)return null;
  const initial=parts[0],surname=parts[parts.length-1];
  const matches=players.filter(p=>{const name=normalize(p.player).split(" ");return name[name.length-1]===surname&&name[0]?.startsWith(initial)});
  return matches.length===1?matches[0]:null;
 };
 const statusLabels={out:"Baja reportada",questionable:"En duda",doubtful:"Dudoso",probable:"Probable",available:"Disponible según fuente",unknown:"Sin estado reportado"};
 const playerCard=(name,label,tone="neutral",index=null)=>{
  const item=el("div",undefined,"nba-player-card nba-player-"+tone);
  if(index!==null)item.append(el("span",String(index+1).padStart(2,"0"),"nba-player-number"));
  item.append(el("strong",name,"nba-player-name"),el("span",label,"nba-player-status"));return item;
 };
 const statusGroup=(title,players,tone)=>{
  const group=el("section",undefined,"nba-status-group nba-status-"+tone);
  const heading=el("h5",undefined,"nba-status-heading");
  heading.append(el("span",title),el("span",String(players.length),"nba-status-count"));group.append(heading);
  const list=el("div",undefined,"nba-player-grid");
  for(const p of players)list.append(playerCard(p.player,statusLabels[p.status]||"Estado sin resolver",tone));
  group.append(list);return group;
 };
 function sportingTeam(team,s){
  const players=Array.isArray(s.players)?[...s.players]:[];
  const starters=(Array.isArray(s.provider_starters)?s.provider_starters:[]).map(raw=>({raw,player:rosterPlayer(raw,players)}));
  const starterIds=new Set(starters.map(x=>x.player?.player_id).filter(Boolean));
  const outs=players.filter(p=>p.status==="out");
  const doubts=players.filter(p=>["questionable","doubtful"].includes(p.status));
  const other=players.filter(p=>!starterIds.has(p.player_id)&&!["out","questionable","doubtful"].includes(p.status));
  const reported=other.filter(p=>["available","probable"].includes(p.status));
  const details=el("details",undefined,"nba-team-details");
  const summary=el("summary",undefined,"nba-team-summary");
  summary.append(el("strong",teamName(team),"nba-team-name"));
  summary.append(el("span",starters.length+" titulares · "+outs.length+" bajas","nba-team-count"));
  details.append(summary);
  const body=el("div",undefined,"nba-team-body");
  body.append(el("p","Disponibilidad observada · "+local(s.observed_at_utc),"nba-capture-time"));
  const lineup=el("section",undefined,"nba-lineup-section");
  const lineupHead=el("div",undefined,"nba-lineup-heading");
  lineupHead.append(el("h4","Quinteto inicial"),el("span",s.lineup_status==="confirmed"?"Confirmado por proveedor":s.lineup_status==="projected"?"Proyectado por proveedor":"Sin confirmación","nba-lineup-badge "+(s.lineup_status==="confirmed"?"is-confirmed":"is-projected")));
  lineup.append(lineupHead);
  if(starters.length){
   const court=el("div","");court.className="nba-lineup-court";
   const note=el("p","Quinteto listado · las posiciones individuales no vienen informadas por la fuente.");note.className="nba-lineup-court__note";
   const surface=el("div","");surface.className="nba-lineup-court__surface";
   surface.setAttribute("role","group");surface.setAttribute("aria-label","Vista de cancha con los titulares listados de "+teamName(team));
   const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
   svg.setAttribute("viewBox","0 0 600 280");svg.setAttribute("preserveAspectRatio","none");svg.setAttribute("aria-hidden","true");svg.classList.add("nba-lineup-court__markings");
   const shapes=[
    ["rect",{x:"5",y:"5",width:"590",height:"270",rx:"5"}],
    ["line",{x1:"300",y1:"5",x2:"300",y2:"275"}],
    ["circle",{cx:"300",cy:"140",r:"34"}],
    ["rect",{x:"5",y:"85",width:"105",height:"110"}],
    ["rect",{x:"490",y:"85",width:"105",height:"110"}],
    ["circle",{cx:"110",cy:"140",r:"35"}],
    ["circle",{cx:"490",cy:"140",r:"35"}]
   ];
   for(const [tag,attrs] of shapes){const shape=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const [key,value] of Object.entries(attrs))shape.setAttribute(key,value);svg.append(shape);}
   surface.append(svg);
   const grid=el("div","");grid.className="nba-lineup-court__players";grid.setAttribute("role","list");
   for(const [index,entry] of starters.entries()){
    const p=entry.player,status=String(p?.status||"").toLowerCase(),name=p?.player||entry.raw;
    const tile=el("div","");tile.className="nba-lineup-court__player";tile.setAttribute("role","listitem");
    const number=el("span",String(index+1).padStart(2,"0"));number.className="nba-lineup-court__number";tile.append(number);
    const playerName=el("strong",name);playerName.className="nba-lineup-court__name";tile.append(playerName);
    if(["out","questionable","doubtful"].includes(status)){
     const icon=el("span",status==="out"?"×":"!");icon.className="nba-lineup-court__injury"+(status==="out"?" is-out":" is-questionable");
     const description=status==="out"?"Fuera según reporte":status==="questionable"?"En duda según reporte":"Dudoso según reporte";
     icon.setAttribute("role","img");icon.setAttribute("aria-label",description);icon.title=description;tile.append(icon);
    }
    grid.append(tile);
   }
   surface.append(grid);court.append(note,surface);lineup.append(court);
  }else lineup.append(el("p","El proveedor no entregó nombres de titulares para esta captura.","nba-section-empty"));
  body.append(lineup);
  if(outs.length||doubts.length){
   const availabilityGrid=el("div","");availabilityGrid.className="nba-availability-grid";
   availabilityGrid.setAttribute("role","group");availabilityGrid.setAttribute("aria-label","Jugadores con baja o en duda para "+teamName(team));
   const addAvailabilityColumn=(title,items,kind)=>{
    const column=el("section","");column.className="nba-availability-grid__column nba-availability-grid__column--"+kind;
    const heading=el("h5",title+" · "+items.length);heading.className="nba-availability-grid__heading";column.append(heading);
    if(items.length){
     const list=el("ul","");list.className="nba-availability-grid__list";
     for(const p of items){
      const row=el("li","");row.className="nba-availability-grid__row";
      const name=el("span",p.player);name.className="nba-availability-grid__name";row.append(name);
      const inDoubt=kind==="doubt",badgeText=inDoubt?(p.status==="doubtful"?"DUDOSO":"EN DUDA"):"OUT";
      const badge=el("span",badgeText);badge.className="nba-availability-grid__badge"+(inDoubt?" nba-availability-grid__badge--doubt":"");
      badge.setAttribute("aria-label",inDoubt?(p.status==="doubtful"?"Dudoso según reporte":"En duda según reporte"):"Baja reportada");row.append(badge);
      list.append(row);
     }
     column.append(list);
    }else{const empty=el("p",kind==="out"?"Sin bajas reportadas.":"Sin jugadores en duda.");empty.className="nba-availability-grid__empty";column.append(empty);}
    availabilityGrid.append(column);
   };
   addAvailabilityColumn("Bajas reportadas",outs,"out");
   addAvailabilityColumn("En duda",doubts,"doubt");
   body.append(availabilityGrid);
  }else body.append(el("p","Esta captura no reporta bajas ni jugadores en duda.","nba-section-empty"));
  if(reported.length){
   const bench=el("details","");bench.className="nba-roster-details";
   const heading=el("summary","Otros estados reportados · "+reported.length+" jugadores · rol en el partido sin confirmar");
   bench.append(heading,statusGroup("Disponible según fuente",reported,"available"),el("p","La fuente publica la plantilla, pero no identifica a estos jugadores como suplentes para el partido.","nba-roster-note"));
   body.append(bench);
  }else if(!outs.length&&!unknown.length&&!doubts.length)body.append(el("p","Esta captura no trae bajas ni dudas individuales reportadas.","nba-section-empty"));
  if(!s.official_injury_status_verified)body.append(el("p","El reporte oficial NBA de lesiones no está verificado en esta captura; los porcentajes no incorporan estas disponibilidades.","nba-source-warning"));
  details.append(body);return details;
 }
 function consolidateGamePanels(){
  if(!agenda||typeof root.querySelector!=="function"||typeof agenda.querySelectorAll!=="function")return;
  const runSection=root.querySelector(".nba-current-run");
  const runTitle=runSection?.querySelector(":scope > h3")?.textContent||"Simulación NBA";
  const runMeta=runSection?.querySelector(":scope > p")?.textContent||"";
  for(const row of [...agenda.querySelectorAll(".daily-match")]){
   const gameId=String(row.dataset.gameId||"");
   if(!gameId)continue;
   const details=document.createElement("details");details.className="nba-game-disclosure";details.dataset.gameId=gameId;
   const summary=document.createElement("summary");summary.className=row.className;
   summary.setAttribute("aria-label","Desplegar simulación de "+row.textContent.trim());
   for(const child of [...row.childNodes])summary.append(child);
   details.append(summary);
   const content=el("div",undefined,"nba-game-disclosure__content");
   const columns=el("div",undefined,"nba-game-disclosure__columns");
   const lineupPanel=el("section",undefined,"nba-game-disclosure__panel nba-game-disclosure__lineup-panel");
   lineupPanel.append(el("h4","Alineaciones y bajas"));
   const evidence=root.querySelector('.nba-forward-game[data-game-id="'+gameId+'"]');
   if(evidence){
    evidence.querySelector("h3")?.remove();
    evidence.className="nba-game-disclosure__section nba-game-disclosure__evidence";
    evidence.querySelectorAll("details").forEach(item=>item.open=true);
    lineupPanel.append(evidence);
   }else lineupPanel.append(el("p","Sin información de alineaciones o disponibilidad para este partido.","nba-game-disclosure__empty"));
   const runPanel=el("section",undefined,"nba-game-disclosure__panel nba-game-disclosure__run-panel");
   runPanel.append(el("h4","Corrida y probabilidades"));
   if(runTitle||runMeta)runPanel.append(el("p",runTitle+(runMeta?" · "+runMeta:""),"nba-game-disclosure__run-meta"));
   const simulation=root.querySelector('.nba-current-run__game[data-game-id="'+gameId+'"]');
   if(simulation){
    if(simulation.dataset&&typeof summary.querySelector==="function"){
     const label=simulation.dataset.probabilityLabel||"Probabilidad del modelo";
     for(const [side,key] of [["away","awayProbability"],["home","homeProbability"]]){
      const team=summary.querySelector(".daily-team-"+side),value=Number(simulation.dataset[key]);
      if(!team||!Number.isFinite(value)||value<=0||value>=1)continue;
      const name=team.querySelector?.(".daily-team-name")?.textContent||team.textContent.trim();
      const badge=document.createElement("span");badge.className="nba-match-probability"+(label.includes("experimental")?" is-experimental":"");badge.textContent=Math.round(value*100)+"%";
      badge.title=label+": "+name+" "+(value*100).toFixed(1)+"%";badge.setAttribute("aria-label",label+": "+name+" "+(value*100).toFixed(1)+" por ciento");team.append(badge);
     }
    }
    simulation.querySelector("h4")?.remove();
    simulation.className="nba-game-disclosure__section nba-game-disclosure__simulation";
    simulation.querySelectorAll("details").forEach(item=>item.open=true);
    runPanel.append(simulation);
   }else runPanel.append(el("p","No hay una corrida publicada para este partido.","nba-game-disclosure__empty"));
   columns.append(lineupPanel,runPanel);
   content.append(columns);
   details.append(content);
   row.replaceWith(details);
  }
  root.replaceChildren();
  root.hidden=true;
  root.style.display="none";
  const progressive=document.getElementById("progressive-forecasts");
  if(progressive){progressive.hidden=true;progressive.style.display="none";}
  const playerStats=document.getElementById("nba-player-projections");
  if(playerStats){playerStats.hidden=true;playerStats.style.display="none";}
 }
 const dateInput=document.getElementById("daily-date");
 const dateInZone=zone=>new Intl.DateTimeFormat("en-CA",{timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
 if(dateInput&&dateInput.value===dateInZone("America/Santiago"))dateInput.value=dateInZone("America/New_York");
 let data=null,currentRun=null,dailySchedule=null,error="";
 function render(){
  root.replaceChildren(el("h2","Resultado de la última corrida NBA"));
  if(agenda)agenda.replaceChildren();
  if(currentRun){
   const selectedDay=document.getElementById("daily-date").value;
   const currentRows=currentRun.predictions.filter(p=>day(p.tipoff_utc)===selectedDay);
   const section=el("section","");section.className="nba-current-run";
   section.append(el("h3","Probabilidad base y escenario por lesiones · corrida #"+currentRun.run_id));
   section.append(el("p","Generada "+local(currentRun.created_at_utc)+" · Los módulos pendientes no bloquean el cálculo base."));
   const injuryCalibration=currentRun.injury_status_calibration;
   if(injuryCalibration?.kind==="nba_injury_status_empirical_summary"){
    const calibration=el("details","");calibration.className="nba-module-run-status";
    calibration.append(el("summary","Evidencia histórica de estados inciertos · "+injuryCalibration.unique_settled_source_claims+" observaciones"));
    for(const group of injuryCalibration.groups||[]){
     const interval=group.played_rate_wilson_95;
     const range=Array.isArray(interval)&&interval.every(Number.isFinite)?" · IC 95% "+(interval[0]*100).toFixed(1)+"–"+(interval[1]*100).toFixed(1)+"%":"";
     calibration.append(el("p",group.source+" · "+group.status+" · jugó "+(group.played_rate*100).toFixed(1)+"% ("+group.played+"/"+group.observations+")"+range,"nba-module-run-status__item"));
    }
    calibration.append(el("p","Frecuencias observadas, separadas por fuente y estado. Son descriptivas; todavía no se usan como pesos de probabilidad."));
    section.append(calibration);
   }
   if(!currentRows.length)section.append(el("p","La última corrida no contiene partidos para la fecha seleccionada."));
   const moduleNames={statistical_baseline:"Probabilidad estadística base",official_injury_report:"Informe oficial de lesiones",starting_lineups:"Quintetos titulares",player_matchups:"Cruces de jugadores",rotation_minutes:"Rotación y minutos",availability_impact:"Impacto de disponibilidad",travel_time_zones:"Viajes y zonas horarias"};
   const statusLabels={included:"Incluido en la predicción",available_not_used:"Datos recibidos; no entran en porcentajes",pending:"Pendiente de publicación o validación",failed:"Falló la consulta",research_scenario:"Afecta el candidato experimental"};
   for(const prediction of currentRows){
    const card=el("article","");card.className="nba-current-run__game";if(card.dataset)card.dataset.gameId=String(prediction.game_id);
    card.append(el("h4",teamName(prediction.away_team)+" — "+teamName(prediction.home_team)));
    const injury=prediction.injury_probability_scenario;
    const baseline=prediction.statistical_baseline_p_home??prediction.hybrid_p_home;
    const modelHome=prediction.model_p_home??baseline;
    const adjustedStatus=["injury_adjusted_research_candidate","matchup_adjusted_research_candidate","travel_adjusted_research_candidate","combined_research_candidate"].includes(prediction.model_probability_status);
    const probabilityCalibrated=currentRun.calibrated===true&&prediction.model_probability_calibrated===true;
    const probabilityLabel=adjustedStatus?"Candidato experimental no calibrado":probabilityCalibrated?"Modelo base calibrado":"Modelo base sin calibración certificada";
    if(typeof modelHome==="number"){
     if(card.dataset&&Number.isFinite(modelHome)&&modelHome>0&&modelHome<1){card.dataset.awayProbability=String(1-modelHome);card.dataset.homeProbability=String(modelHome);card.dataset.probabilityLabel=probabilityLabel;}
     card.append(el("p",(adjustedStatus?"Candidato experimental (no calibrado): ":probabilityCalibrated?"Modelo base calibrado: ":"Modelo base (sin calibración certificada): ")+teamName(prediction.away_team)+" "+((1-modelHome)*100).toFixed(1)+"% · "+teamName(prediction.home_team)+" "+(modelHome*100).toFixed(1)+"%","nba-model-probability"));
    }
    const market=marketPanel(prediction,modelHome,prediction.point_projection);if(market)card.append(market);
    if(adjustedStatus&&typeof baseline==="number")card.append(el("p","Referencia estadística sin ajustes: "+teamName(prediction.away_team)+" "+((1-baseline)*100).toFixed(1)+"% · "+teamName(prediction.home_team)+" "+(baseline*100).toFixed(1)+"%"));
    if(["research_scenario","partial_research_scenario"].includes(injury?.status)){
     const partial=injury.status==="partial_research_scenario";
     const delta=Number(injury.home_probability_delta_pp||0);
     const direction=delta>0?"+" :"";
     card.append(el("p",(partial?"Ajuste parcial por bajas: ":"Cambio aplicado por bajas: ")+direction+delta.toFixed(1)+" puntos porcentuales para "+teamName(prediction.home_team)+". El candidato mostrado ya incorpora este cambio.","nba-injury-scenario"));
     const evidence=el("details","");evidence.className="nba-module-run-status";
     evidence.append(el("summary",partial?"Bajas incluidas y excluidas por falta de historial":"Bajas y redistribución estimada"));
     for(const team of [prediction.away_team,prediction.home_team]){
      const impact=injury.teams?.[team];if(!impact)continue;
      const included=impact.quantified_out_players||impact.accepted_out_players||impact.out_players||[];
      const outNames=included.map(player=>player.player).filter(Boolean);
      let line=teamName(team)+": "+(outNames.length?"incluidas en el cálculo: "+outNames.join(", "):"sin baja cuantificable");
      const lost=impact.estimated_points_lost_per_game??impact.historical_output_loss_per_game?.points;
      const gained=impact.estimated_points_added_by_replacements_per_game??impact.historical_output_from_added_minutes_per_game?.points;
      if(Number.isFinite(lost))line+=" · "+lost.toFixed(1)+" puntos históricos perdidos";
      if(Number.isFinite(gained))line+=" · "+gained.toFixed(1)+" puntos redistribuidos";
      evidence.append(el("p",line,"nba-module-run-status__item nba-module-run-status__item--research_scenario"));
      for(const player of impact.unquantified_out_players||[]){
       const name=player.player||player.player_id||"jugador";
       const fields=(impact.players_without_required_history||[]).filter(value=>value.startsWith(String(player.player_id)+":")).map(value=>value.split(":").slice(1).join(":"));
       evidence.append(el("p",teamName(team)+": "+name+" confirmado fuera, excluido del cálculo por falta de historial de "+(fields.join(", ")||"minutos o puntos")+".","nba-module-run-status__item nba-module-run-status__item--pending"));
      }
     }
     evidence.append(el("p",partial?"Escenario parcial: solo bajas con historial suficiente entran en la estimación. Las ausencias listadas como excluidas no se imputaron ni se les inventaron minutos o puntos. Experimental, no calibrado ni aprobado para producción.":"Estimación basada en minutos redistribuidos y producción histórica; dudas y estados sin confirmar no se consideran bajas. Escenario experimental, no calibrado ni aprobado para producción."));
     card.append(evidence);
    }else if(injury?.status==="blocked"){
     card.append(el("p","Sin ajuste por lesiones: "+(injury.reason||"faltan datos verificables.")+" Se conserva la probabilidad base.","nba-module-run-status__item nba-module-run-status__item--failed"));
    }else if(injury?.status==="no_confirmed_out_claims"){
     card.append(el("p","Sin bajas OUT oficiales asociadas; se conserva la probabilidad base."));
    }
    const statusRange=injury?.uncertain_status_probability_range||injury?.multi_source_scenario?.uncertain_status_probability_range;
    if(statusRange?.status==="conditional_probability_range"){
     const low=Number(statusRange.home_probability_min),high=Number(statusRange.home_probability_max);
     if(Number.isFinite(low)&&Number.isFinite(high)){
      card.append(el("p","Dudas y dudosos · escenario condicional para "+teamName(prediction.home_team)+": "+(low*100).toFixed(1)+"–"+(high*100).toFixed(1)+"%. "+statusRange.scenario_count+" combinaciones; sin ponderar ni reemplazar el porcentaje central.","nba-injury-range"));
      const rangeDetails=el("details","");rangeDetails.className="nba-module-run-status";
      rangeDetails.append(el("summary","Ver estados inciertos y escenarios"));
      for(const player of statusRange.players||[]){
       rangeDetails.append(el("p",teamName(player.team)+": "+player.player+" · "+(player.status==="doubtful"?"dudoso":"cuestionable")+" · "+(player.source_class==="official_nba_report"?"informe oficial":"coincidencia CBS + ESPN"),"nba-module-run-status__item"));
      }
      for(const [index,branch] of (statusRange.branches||[]).entries()){
       const assumed=(branch.assumptions||[]).map(item=>item.player+" "+(item.assumption==="out"?"fuera":"disponible")).join("; ")||"sin dudas";
       rangeDetails.append(el("p","#"+(index+1)+" · "+assumed+" · "+(Number(branch.home_probability)*100).toFixed(1)+"% "+teamName(prediction.home_team),"nba-module-run-status__item"));
      }
      rangeDetails.append(el("p","Cada combinación estima el impacto de minutos y puntos históricos si esas personas juegan o quedan fuera. No se asignan probabilidades de disponibilidad hasta contar con una muestra para calibrarlas."));
      card.append(rangeDetails);
     }
    }else if(["incomplete_uncertain_evidence","too_many_uncertain_players","blocked"].includes(statusRange?.status)){
     card.append(el("p","Sin rango para las dudas: "+(statusRange.reason||statusRange.status)+". Se conserva el escenario disponible.","nba-module-run-status__item nba-module-run-status__item--pending"));
    }
    const matchup=prediction.player_matchup_probability_scenario;
    if(matchup){
     const evidence=el("details","");evidence.className="nba-module-run-status";
     evidence.append(el("summary","Cruces históricos y quinteto estimado"));
     if(matchup.status==="research_scenario"){
      evidence.append(el("p","Variación estimada del margen local: "+Number(matchup.estimated_home_margin_delta_per_100_possessions||0).toFixed(2)+" puntos por 100 posesiones. Asignaciones aproximadas por posición; no son marcas confirmadas."));
      for(const team of [prediction.away_team,prediction.home_team]){
       const teamData=matchup.teams?.[team];if(!teamData)continue;
       for(const pair of teamData.assignments||[]){
        if(pair.status!=="historical_pair_sample_usable")continue;
        evidence.append(el("p",teamName(team)+": "+(pair.offense_player.player||pair.offense_player.player_id)+" vs "+(pair.defender_player.player||pair.defender_player.player_id)+" · historial "+Number(pair.partial_possessions).toFixed(0)+" posesiones parciales"));
       }
      }
      evidence.append(el("p","Escenario experimental no calibrado. El proveedor registra cruces anteriores; el emparejamiento de hoy se estima con las posiciones del quinteto."));
     }else{
      evidence.append(el("p","Sin ajuste por cruces: "+(matchup.reason||"faltan datos verificables.")+" Se conserva el resto del candidato."));
     }
     card.append(evidence);
    }
    const travelScenario=prediction.travel_probability_scenario;
    const travelTeams=prediction.supporting_modules?.travel_time_zones?.data?.teams;
    if(travelScenario||travelTeams){
     const details=el("details","");details.className="nba-module-run-status";
     details.append(el("summary","Descanso · B2B · viajes y husos horarios"));
     const pathLabels={home_to_home:"local → local",home_to_road:"local → visita",road_to_home:"visita → local",road_to_road:"visita → visita"};
     const showNumber=(value,digits=0)=>typeof value==="number"&&Number.isFinite(value)?value.toFixed(digits):"—";
     for(const team of [prediction.away_team,prediction.home_team]){
      const context=travelTeams?.[team];if(!context)continue;
      const role=context.is_home?"Local":"Visita";
      const b2b=context.is_back_to_back?"B2B":"Sin B2B";
      const route=context.back_to_back_path?pathLabels[context.back_to_back_path]||context.back_to_back_path:null;
      let line=teamName(team)+" · "+role+" · "+b2b;
      line+=" · "+(context.rest_days===null||context.rest_days===undefined?"descanso sin historial":context.rest_days+" día"+(context.rest_days===1?"":"s")+" de descanso");
      if(route)line+=" · "+route;
      line+=" · viaje reciente "+showNumber(context.cumulative_travel_km_last_7_days)+" km";
      if(context.timezone_shift_hours!==null&&context.timezone_shift_hours!==undefined){
       const shift=context.timezone_shift_hours, direction=shift>0?"hacia el este":shift<0?"hacia el oeste":"sin cambio de huso";
       line+=" · cambio horario "+(shift>0?"+":"")+showNumber(shift,1)+" h "+direction;
      }
      line+=" · partidos: "+showNumber(context.games_last_4_days)+"/4 días, "+showNumber(context.games_last_7_days)+"/7 días";
      if(context.body_clock_tipoff_hour!==null&&context.body_clock_tipoff_hour!==undefined)line+=" · inicio según reloj previo "+showNumber(context.body_clock_tipoff_hour,1)+" h";
      details.append(el("p",line,"nba-module-run-status__item"));
     }
     if(travelScenario?.status==="research_scenario"&&travelScenario.applied){
      const probability=travelScenario.travel_adjusted_home_probability;
      details.append(el("p","Candidato experimental del módulo: "+(typeof probability==="number"?(probability*100).toFixed(1)+"% para "+teamName(prediction.home_team):"porcentaje no disponible")+" · el ajuste superó el corte cronológico de esta ejecución; no está certificado.","nba-module-run-status__item nba-module-run-status__item--research_scenario"));
     }else{
      const reason=travelScenario?.status==="holdout_no_improvement"?"la validación no mejoró Brier y log loss":travelScenario?.status==="insufficient_chronological_sample"?"la muestra cronológica aún es insuficiente":"no hay evidencia suficiente";
      details.append(el("p","Los datos de descanso y viaje se muestran como contexto; esta ejecución no aplicó un ajuste porcentual porque "+reason+".","nba-module-run-status__item nba-module-run-status__item--pending"));
     }
     details.append(el("p","B2B se estima con fechas locales y horas entre inicios; los kilómetros son una ruta geográfica aproximada, no el itinerario real del equipo."));
     card.append(details);
    }
    const playerStats=prediction.player_stat_projections;
    if(playerStats){
     const statsDetails=el("details","");statsDetails.className="nba-module-run-status nba-player-stat-projections";
     statsDetails.append(el("summary","Puntos · rebotes · asistencias por jugador"));
     statsDetails.append(el("p","Estimación basada en producción histórica por minuto y minutos previstos; no es una línea de apuestas ni modifica la probabilidad del partido."));
     for(const team of [prediction.away_team,prediction.home_team]){
      const teamData=playerStats.teams?.[team];if(!teamData)continue;
      const adjustedPlayers=(teamData.players||[]).filter(player=>player.injury_adjustment_status==="applied").length;
       const adjustmentLabel=adjustedPlayers?(" · "+adjustedPlayers+" con minutos ajustados por bajas"):(teamData.injury_projection_adjustment_status==="available"?" · escenario de bajas sin cambio individual":" · ajuste por bajas no calculable");
       const teamHeading=el("h5",teamName(team)+(teamData.roster_verified?" · plantilla verificada":" · plantilla sin verificar")+adjustmentLabel);teamHeading.className="nba-player-stat-projections__team";statsDetails.append(teamHeading);
      if(!teamData.players?.length){statsDetails.append(el("p","No hay plantilla disponible para proyectar.","nba-section-empty"));continue;}
      for(const player of teamData.players){
       const row=el("div","");row.className="nba-player-stat-projections__player";
       const role=player.role==="starter_listed_by_provider"?"Titular listado":"Rol sin confirmar";
       const availabilityLabels={out:"Fuera según reporte",unknown:"Disponibilidad sin confirmar",questionable:"En duda",doubtful:"Dudoso",probable:"Probable",available:"Disponible según fuente"};
       const availability=availabilityLabels[player.availability_status]?" · "+availabilityLabels[player.availability_status]:"";
       const minuteBasis=player.minutes_source==="injury_conditional_minute_redistribution"?"minutos redistribuidos por bajas":player.minutes_source==="availability_adjusted_team_allocation"?"minutos ajustados por disponibilidad":"minutos históricos";
       const identity=el("span",undefined,"nba-player-stat-projections__identity");
       const name=el("strong",player.player);name.className="nba-player-stat-projections__name";identity.append(name);
       const badges=el("span",undefined,"nba-player-stat-projections__badges");
       if(player.role==="starter_listed_by_provider"){const badge=el("span","★ STARTER","nba-player-stat-projections__badge nba-player-stat-projections__badge--starter");badge.title="Titular listado por el proveedor";badge.setAttribute("aria-label","Titular listado por el proveedor");badges.append(badge);}
       if(player.availability_status==="out"){const badge=el("span","✕ OUT","nba-player-stat-projections__badge nba-player-stat-projections__badge--out");badge.title="Baja reportada por la fuente";badge.setAttribute("aria-label","Baja reportada por la fuente");badges.append(badge);}
       if(badges.childNodes.length)identity.append(badges);
       row.append(identity);
       const meta=el("span",role+availability+" · "+(player.projected_minutes===null?"min —":"min "+player.projected_minutes.toFixed(1))+" · "+minuteBasis+" · "+player.historical_games+" PJ");meta.className="nba-player-stat-projections__meta";row.append(meta);
       const metrics=el("div","");metrics.className="nba-player-stat-projections__metrics";
       for(const [key,label,baseKey,deltaKey] of [
        ["points_projection","PTS","baseline_points_projection","injury_delta_points_projection"],
        ["rebounds_projection","REB","baseline_rebounds_projection","injury_delta_rebounds_projection"],
        ["assists_projection","AST","baseline_assists_projection","injury_delta_assists_projection"]
       ]){
        const value=player[key],sample=player[key.replace("_projection","_sample_games")];
        let metricText=label+" "+(typeof value==="number"?value.toFixed(1):"—");
        if(player.injury_adjustment_status==="applied"&&typeof player[baseKey]==="number"&&typeof player[deltaKey]==="number"){
         const delta=player[deltaKey],sign=delta>0?"+":"";
         metricText+=" · base "+player[baseKey].toFixed(1)+" ("+sign+delta.toFixed(1)+")";
        }
        if(sample)metricText+=" · n="+sample;
        const metric=el("span",metricText);metric.className="nba-player-stat-projections__metric";metrics.append(metric);
       }
       if(player.projection_reason==="insufficient_historical_sample"){const notice=el("span","Muestra insuficiente");notice.className="nba-player-stat-projections__notice";row.append(notice);}
       if(player.projection_reason==="insufficient_minutes_evidence"){const notice=el("span","Minutos insuficientes");notice.className="nba-player-stat-projections__notice";row.append(notice);}
       row.append(metrics);statsDetails.append(row);
      }
     }
     card.append(statsDetails);
    }
    const details=el("details","");details.className="nba-module-run-status";
    details.append(el("summary","Módulos usados y pendientes"));
    for(const [key,module] of Object.entries(prediction.supporting_modules||{})){
     const state=module.status||(module.entered_prediction?"included":module.connected?"available_not_used":"pending");
     const line=el("p",(statusLabels[state]||"Estado sin clasificar")+" · "+(moduleNames[key]||key)+(module.detail?" — "+module.detail:""));
     line.className="nba-module-run-status__item nba-module-run-status__item--"+state;
     details.append(line);
    }
    card.append(details);section.append(card);
   }
   root.append(section);
  }
  if(!data){
   const label=document.getElementById("daily-label"),source=document.getElementById("feed-message");
   if(label)label.textContent="NBA · Registro prospectivo";
   if(source)source.textContent=error||"Cargando el registro NBA…";
   root.append(el("p",error||"Cargando el registro NBA…"));return;
  }
  const selected=document.getElementById("daily-date").value,rows=calendarGames(data,dailySchedule,selected);
  const label=document.getElementById("daily-label"),source=document.getElementById("feed-message");
  if(label)label.textContent="NBA · "+selected+" · "+rows.length+" partido"+(rows.length===1?" registrado":"s registrados");
  if(source)source.textContent="Jornada NBA según fecha oficial de EE. UU. · horarios de Chile · captura "+local(data.last_source_capture_utc)+"."+(rows.some(game=>game.calendar_only)?" · hay partidos sin emisión en la última corrida.":"");
  root.append(el("p","Elo y Challenger experimentales · los ajustes de lesiones, quintetos, cruces y viajes dependen de evidencia suficiente."));
  root.append(el("p","Última captura: "+local(data.last_source_capture_utc)+(stale(data)?" · Datos desactualizados; revisar la fuente.":"")));
  if(data.source_error_count)root.append(el("p","El registro conserva fallos de fuente. La cobertura requiere revisión."));
  if(data.sporting_evidence_errors.length)root.append(el("p","Hay evidencia deportiva que no pudo verificarse."));
  if(!rows.length){const empty="La fecha elegida todavía no tiene cobertura suficiente en el calendario NBA.";root.append(el("p",empty));if(agenda)agenda.append(el("p",empty));}
  for(const g of rows){
   const card=el("article","");card.className="nba-forward-game";
   const state=g.outcome?"Final":g.source_state==="in"?"En juego al último corte":g.source_status==="STATUS_FINAL"?"Final · cierre emparejado pendiente":g.source_status==="STATUS_POSTPONED"?"Aplazado":g.source_status==="STATUS_CANCELED"?"Cancelado":g.status.includes("review")?"Requiere revisión":Date.now()>=Date.parse(g.tipoff_utc)?"Sin actualización posterior al inicio":"Por comenzar";
   const matchData={sport:"nba",id:g.game_id,away:g.away_team,home:g.home_team,start_utc:g.tipoff_utc,status:g.source_status||g.status,completed:Boolean(g.outcome),away_score:g.outcome?.away_points,home_score:g.outcome?.home_points};
   const latest=currentRun?.predictions.find(row=>String(row.game_id)===String(g.game_id)&&row.tipoff_utc===g.tipoff_utc);
   const market=latest?.market_context||g.market_context;
   const modelHome=latest?(latest.model_p_home??latest.statistical_baseline_p_home??latest.hybrid_p_home):null;
   if(g.calendar_only){
    const calendarRow=window.PulsoCalendar?.makeMatchRow(matchData,{sport:"nba"});
    if(calendarRow?.dataset)calendarRow.dataset.gameId=String(g.game_id);
    if(agenda){agenda.append(calendarRow||el("p",teamName(g.away_team)+" — "+teamName(g.home_team)+" · "+local(g.tipoff_utc)+" · Por comenzar"));agenda.append(marketCalendarStrip(g,market,modelHome));}
    const card=el("article","");card.className="nba-forward-game nba-forward-game--calendar-only";
    card.append(el("h3",teamName(g.away_team)+" — "+teamName(g.home_team)));
    card.append(el("p",local(g.tipoff_utc)+" · Partido del calendario diario"));
    if(latest){
     card.append(el("p","Pronóstico disponible en la última corrida; aún no está incorporado al registro prospectivo."));
     const marketDetails=marketPanel({...g,market_context:market,first_prediction:latest},modelHome);
     if(marketDetails)card.append(marketDetails);
    }else card.append(el("p","Este encuentro no aparece en la última corrida NBA; todavía no hay pronóstico ni análisis de alineaciones publicado."));
    if(card.dataset)card.dataset.gameId=String(g.game_id);root.append(card);continue;
   }
   const calendarRow=window.PulsoCalendar?.makeMatchRow(matchData,{sport:"nba",stateText:state});
   if(calendarRow?.dataset)calendarRow.dataset.gameId=String(g.game_id);
   if(agenda){agenda.append(calendarRow||el("p",teamName(g.away_team)+" — "+teamName(g.home_team)+" · "+local(g.tipoff_utc)+" · "+state));agenda.append(marketCalendarStrip(g,market,modelHome));}
   if(card.dataset)card.dataset.gameId=String(g.game_id);
   card.append(el("h3",teamName(g.away_team)+" — "+teamName(g.home_team)));
   card.append(el("p",local(g.tipoff_utc)+" · "+state));
   if(g.outcome)card.append(el("p","Resultado final: "+g.outcome.away_points+" — "+g.outcome.home_points));
   const p=g.first_prediction;
   if(p&&!g.issues.length){
    card.append(el("p","Emisión pregame original: "+local(p.prediction_as_of_utc)));
    for(const [name,key] of [["Elo","elo_p_home"],["Challenger","challenger_p_home"]])card.append(el("p",name+": "+teamName(g.away_team)+" "+((1-p[key])*100).toFixed(1)+"% · "+teamName(g.home_team)+" "+(p[key]*100).toFixed(1)+"%"));
    const marketGame={...g,market_context:market,first_prediction:latest||g.first_prediction};
    const marketDetails=marketPanel(marketGame,modelHome);if(marketDetails)card.append(marketDetails);
   }else card.append(el("p",g.issues.length?"PASS · La emisión original requiere revisión por cambios de la ficha.":"PASS · No hay una pareja de pronósticos pregame válida."));
   if(g.issues.length)card.append(el("p","El partido presenta cambios o conflictos de fuente; requiere revisión."));
   for(const team of [g.away_team,g.home_team]){
    const s=g.sporting[team];
    if(!s){card.append(el("p",teamName(team)+": disponibilidad pregame sin cobertura.","nba-coverage-empty"));continue;}
    card.append(sportingTeam(team,s));
   }
   card.append(el("p","Modelo deportivo integrado y ventaja +20: PASS. "+(data.evaluation_status==="window_open_metrics_withheld"?"Validación prospectiva en curso.":"Ventana cerrada; falta la auditoría final.")));root.append(card);
  }
  consolidateGamePanels();
 }
 document.getElementById("daily-date").addEventListener("change",render);render();
 window.PulsoNbaForward={ready:(async()=>{try{
  const [response,currentResponse,dailyResponse]=await Promise.all([
   fetch("./data/nba-forward-latest.json",{cache:"no-store"}),
   fetch("./data/nba-predictions-latest.json",{cache:"no-store"}).catch(()=>null),
   fetch("./data/daily.json",{cache:"no-store"}).catch(()=>null)
  ]);
  if(!response.ok)throw Error("source");const x=await response.json();if(!validate(x))throw Error("contract");data=x;
  if(dailyResponse?.ok){try{const schedule=await dailyResponse.json();if(schedule?.data_kind==="fixtures_and_results_only"&&Array.isArray(schedule.games))dailySchedule=schedule;}catch{}}
  if(currentResponse?.ok){
   const latest=await currentResponse.json();
   if(latest?.kind==="nba_pulso_research_publication_v1"&&stamp(latest.created_at_utc)&&Array.isArray(latest.predictions))currentRun=latest;
  }
  if(currentRun){const marketById=new Map(x.games.map(game=>[String(game.game_id),game]));for(const prediction of currentRun.predictions){const game=marketById.get(String(prediction.game_id));if(game&&game.tipoff_utc===prediction.tipoff_utc&&validMarket(game.market_context,game.tipoff_utc))prediction.market_context=game.market_context;}}

 }catch{error="No se pudo cargar un registro NBA válido. No se muestran porcentajes de otra emisión.";}render();})()};
})();
