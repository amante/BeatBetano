"use strict";
(function(){
 const panel=document.getElementById("nba-player-projections");
 const dateInput=document.getElementById("daily-date");
 if(!panel||!dateInput||new URLSearchParams(location.search).get("sport")!=="nba")return;
 const names={ATL:"Atlanta Hawks",BOS:"Boston Celtics",BKN:"Brooklyn Nets",CHA:"Charlotte Hornets",CHI:"Chicago Bulls",CLE:"Cleveland Cavaliers",DAL:"Dallas Mavericks",DEN:"Denver Nuggets",DET:"Detroit Pistons",GSW:"Golden State Warriors",HOU:"Houston Rockets",IND:"Indiana Pacers",LAC:"LA Clippers",LAL:"Los Angeles Lakers",MEM:"Memphis Grizzlies",MIA:"Miami Heat",MIL:"Milwaukee Bucks",MIN:"Minnesota Timberwolves",NOP:"New Orleans Pelicans",NYK:"New York Knicks",OKC:"Oklahoma City Thunder",ORL:"Orlando Magic",PHI:"Philadelphia 76ers",PHX:"Phoenix Suns",POR:"Portland Trail Blazers",SAC:"Sacramento Kings",SAS:"San Antonio Spurs",TOR:"Toronto Raptors",UTA:"Utah Jazz",WAS:"Washington Wizards"};
 const teamName=code=>names[code]||code;
 const day=value=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(value));
 const local=value=>new Date(value).toLocaleString("es-CL",{timeZone:"America/Santiago"});
 const node=(tag,text,cls)=>{const item=document.createElement(tag);if(text!==undefined)item.textContent=text;if(cls)item.className=cls;return item;};
 const metric=(value)=>typeof value==="number"&&Number.isFinite(value)?value.toFixed(1):"—";
 let feed=null,loadError="";
 function playerRow(player){
  const row=node("article",undefined,"nba-player-stat-projections__player");
  row.append(node("strong",player.player||"Jugador sin nombre","nba-player-stat-projections__name"));
  const role=player.role==="starter_listed_by_provider"?"Titular listado":"Rol sin confirmar";
  const status={out:"Baja reportada",questionable:"En duda",doubtful:"Dudoso",probable:"Probable",available:"Disponible según fuente",unknown:"Estado sin confirmar"}[player.availability_status]||"Estado sin confirmar";
  const minuteSource=player.minutes_source==="availability_adjusted_team_allocation"?"min ajustados":"min históricos";
  const minutes=typeof player.projected_minutes==="number"?player.projected_minutes.toFixed(1):"—";
  const meta=node("span",role+" · "+status+" · "+minutes+" "+minuteSource+" · "+(player.historical_games||0)+" PJ","nba-player-stat-projections__meta");
  row.append(meta);
  const metrics=node("div",undefined,"nba-player-stat-projections__metrics");
  for(const [key,label] of [["points_projection","PTS"],["rebounds_projection","REB"],["assists_projection","AST"]]){
   const sample=player[key.replace("_projection","_sample_games")];
   metrics.append(node("span",label+" "+metric(player[key])+(sample?" · n="+sample:""),"nba-player-stat-projections__metric"));
  }
  row.append(metrics);
  if(player.projection_status==="unavailable")row.append(node("span","Sin proyección · baja reportada","nba-player-stat-projections__notice"));
  else if(player.projection_reason==="insufficient_historical_sample")row.append(node("span","Muestra histórica insuficiente","nba-player-stat-projections__notice"));
  else if(player.projection_reason==="insufficient_minutes_evidence")row.append(node("span","Sin minutos previstos suficientes","nba-player-stat-projections__notice"));
  return row;
 }
 function render(){
  panel.hidden=false;
  panel.replaceChildren(node("div",undefined,"nba-player-projections-panel__header"));
  const header=panel.firstElementChild;
  header.append(node("div","NBA · DESGLOSE POR JUGADOR","eyebrow"),node("h2","Puntos, rebotes y asistencias"));
  if(loadError){panel.append(node("p",loadError,"nba-player-projections-panel__message nba-player-projections-panel__message--error"));return;}
  if(!feed){panel.append(node("p","Cargando las proyecciones publicadas…","nba-player-projections-panel__message"));return;}
  const selected=dateInput.value;
  const games=feed.predictions.filter(game=>day(game.tipoff_utc)===selected);
  panel.append(node("p","Corrida #"+feed.run_id+" · publicada "+local(feed.created_at_utc)+". Estimaciones históricas por jugador; no son líneas de apuestas ni modifican el ganador del partido.","nba-player-projections-panel__note"));
  if(!games.length){panel.append(node("p","No hay partidos con proyecciones para la fecha seleccionada.","nba-player-projections-panel__message"));return;}
  let shown=0;
  for(const game of games){
   const stats=game.player_stat_projections;
   const teams=stats?.teams||{};
   const players=[...(teams[game.away_team]?.players||[]),...(teams[game.home_team]?.players||[])];
   if(!stats)continue;
   shown++;
   const details=node("details",undefined,"nba-player-projections-panel__game");
   details.append(node("summary",teamName(game.away_team)+" — "+teamName(game.home_team)+" · "+players.length+" jugadores"));
   for(const code of [game.away_team,game.home_team]){
    const team=teams[code];if(!team)continue;
    const group=node("section",undefined,"nba-player-projections-panel__team");
    group.append(node("h3",teamName(code)+(team.roster_verified?" · plantilla verificada":" · plantilla sin verificar")));
    if(!Array.isArray(team.players)||!team.players.length)group.append(node("p","No hay jugadores disponibles para este equipo."));
    else for(const player of team.players)group.append(playerRow(player));
    details.append(group);
   }
   panel.append(details);
  }
  if(!shown)panel.append(node("p","La última corrida todavía no tiene estadísticas individuales publicadas para esta fecha.","nba-player-projections-panel__message"));
 }
 async function load(){
  loadError="";feed=null;render();
  try{
   const url="./data/nba-predictions-latest.json?pulso="+Date.now();
   const response=await fetch(url,{cache:"no-store"});
   if(!response.ok)throw new Error("feed");
   const data=await response.json();
   if(data?.kind!=="nba_pulso_research_publication_v1"||!Array.isArray(data.predictions)||!data.predictions.every(game=>game&&game.game_id&&game.tipoff_utc))throw new Error("contract");
   feed=data;
  }catch{loadError="No se pudo cargar el registro de proyecciones NBA. Intenta actualizar la página."; }
  render();
 }
 dateInput.addEventListener("change",render);
 load();
 window.PulsoNbaPlayerProjections={refresh:load};
})();
