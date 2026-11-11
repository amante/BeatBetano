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
 const teamNames={ATL:"Atlanta Hawks",BOS:"Boston Celtics",BKN:"Brooklyn Nets",CHA:"Charlotte Hornets",CHI:"Chicago Bulls",CLE:"Cleveland Cavaliers",DAL:"Dallas Mavericks",DEN:"Denver Nuggets",DET:"Detroit Pistons",GS:"Golden State Warriors",GSW:"Golden State Warriors",HOU:"Houston Rockets",IND:"Indiana Pacers",LAC:"LA Clippers",LAL:"Los Angeles Lakers",MEM:"Memphis Grizzlies",MIA:"Miami Heat",MIL:"Milwaukee Bucks",MIN:"Minnesota Timberwolves",NO:"New Orleans Pelicans",NOP:"New Orleans Pelicans",NY:"New York Knicks",NYK:"New York Knicks",OKC:"Oklahoma City Thunder",ORL:"Orlando Magic",PHI:"Philadelphia 76ers",PHX:"Phoenix Suns",POR:"Portland Trail Blazers",SA:"San Antonio Spurs",SAS:"San Antonio Spurs",SAC:"Sacramento Kings",TOR:"Toronto Raptors",UTA:"Utah Jazz",UTAH:"Utah Jazz",WAS:"Washington Wizards",WSH:"Washington Wizards"};
 const teamName=code=>teamNames[code]||code;
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
  const unknown=other.filter(p=>!p.status||p.status==="unknown").sort((a,b)=>a.player.localeCompare(b.player,"es"));
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
   const grid=el("div",undefined,"nba-player-grid nba-starters-grid");
   for(const [index,entry] of starters.entries()){
    const p=entry.player,reportedStatus=p&&p.status&&p.status!=="unknown";
    const label=p?.status==="out"?"Baja reportada · revisar quinteto":p&&["questionable","doubtful"].includes(p.status)?"En duda según fuente":reportedStatus?statusLabels[p.status]:"Titular listado · disponibilidad sin confirmar";
    const tone=p?.status==="out"?"out":p&&["questionable","doubtful"].includes(p.status)?"doubt":"starter";
    grid.append(playerCard(p?.player||entry.raw,label,tone,index));
   }
   lineup.append(grid);
  }else lineup.append(el("p","El proveedor no entregó nombres de titulares para esta captura.","nba-section-empty"));
  body.append(lineup);
  if(outs.length)body.append(statusGroup("Bajas reportadas",outs,"out"));
  if(doubts.length)body.append(statusGroup("En duda",doubts,"doubt"));
  const bench=el("details",undefined,"nba-roster-details");
  bench.append(el("summary","Resto de la plantilla · "+other.length+" jugadores · banca sin confirmar"));
  if(reported.length)bench.append(statusGroup("Disponibilidad reportada",reported,"available"));
  const unknownDetails=el("details",undefined,"nba-unknown-details");
  unknownDetails.append(el("summary","Sin estado en el reporte · "+unknown.length));
  if(unknown.length){
   const list=el("ul",undefined,"nba-unknown-list");
   for(const p of unknown)list.append(el("li",p.player));
   unknownDetails.append(list);
  }else unknownDetails.append(el("p","Todos los jugadores restantes tienen un estado reportado."));
  bench.append(unknownDetails,el("p","La fuente publica la plantilla, pero no identifica a estos jugadores como suplentes para el partido.","nba-roster-note"));
  body.append(bench);
  if(!s.official_injury_status_verified)body.append(el("p","El reporte oficial NBA de lesiones no está verificado en esta captura; los porcentajes no incorporan estas disponibilidades.","nba-source-warning"));
  details.append(body);return details;
 }
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
   const card=el("article","");card.append(el("h3",teamName(g.away_team)+" — "+teamName(g.home_team)));
   const state=g.outcome?"Final":g.source_state==="in"?"En juego al último corte":g.source_status==="STATUS_FINAL"?"Final · cierre emparejado pendiente":g.source_status==="STATUS_POSTPONED"?"Aplazado":g.source_status==="STATUS_CANCELED"?"Cancelado":g.status.includes("review")?"Requiere revisión":Date.now()>=Date.parse(g.tipoff_utc)?"Sin actualización posterior al inicio":"Por comenzar";
   card.append(el("p",local(g.tipoff_utc)+" · "+state));
   const p=g.first_prediction;
   if(p&&!g.issues.length){
    card.append(el("p","Emisión pregame original: "+local(p.prediction_as_of_utc)));
    for(const [name,key] of [["Elo","elo_p_home"],["Challenger","challenger_p_home"]])card.append(el("p",name+": "+teamName(g.away_team)+" "+((1-p[key])*100).toFixed(1)+"% · "+teamName(g.home_team)+" "+(p[key]*100).toFixed(1)+"%"));
   }else card.append(el("p",g.issues.length?"PASS · La emisión original requiere revisión por cambios de la ficha.":"PASS · No hay una pareja de pronósticos pregame válida."));
   if(g.issues.length)card.append(el("p","El partido presenta cambios o conflictos de fuente; requiere revisión."));
   if(g.outcome)card.append(el("p","Marcador final: "+teamName(g.away_team)+" "+g.outcome.away_points+" — "+teamName(g.home_team)+" "+g.outcome.home_points));
   for(const team of [g.away_team,g.home_team]){
    const s=g.sporting[team];
    if(!s){card.append(el("p",teamName(team)+": disponibilidad pregame sin cobertura.","nba-coverage-empty"));continue;}
    card.append(sportingTeam(team,s));
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
