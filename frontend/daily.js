"use strict";
const $=id=>document.getElementById(id);
const SPORTS={nba:"NBA",nfl:"NFL",nhl:"NHL",soccer:"Fútbol",tennis:"Tenis"};
const qs=new URLSearchParams(location.search),sport=qs.get("sport");
if(!Object.hasOwn(SPORTS,sport)){location.replace("./index.html");throw Error("Seleccione una disciplina desde la portada");}
// Shared markup is owned by one discipline; keep it out of every other route.
document.querySelectorAll('[data-sport-only]').forEach(panel=>{
 const visible=panel.dataset.sportOnly===sport;
 panel.hidden=!visible;panel.style.display=visible?"":"none";
});
const title=SPORTS[sport];
const NHL_TEAMS={ANA:"Anaheim Ducks",BOS:"Boston Bruins",BUF:"Buffalo Sabres",CAR:"Carolina Hurricanes",CBJ:"Columbus Blue Jackets",CGY:"Calgary Flames",CHI:"Chicago Blackhawks",COL:"Colorado Avalanche",DAL:"Dallas Stars",DET:"Detroit Red Wings",EDM:"Edmonton Oilers",FLA:"Florida Panthers",LAK:"Los Angeles Kings",MIN:"Minnesota Wild",MTL:"Montreal Canadiens",NJD:"New Jersey Devils",NSH:"Nashville Predators",NYI:"New York Islanders",NYR:"New York Rangers",OTT:"Ottawa Senators",PHI:"Philadelphia Flyers",PIT:"Pittsburgh Penguins",SEA:"Seattle Kraken",SJS:"San Jose Sharks",STL:"St. Louis Blues",TBL:"Tampa Bay Lightning",TOR:"Toronto Maple Leafs",UTA:"Utah Mammoth",VAN:"Vancouver Canucks",VGK:"Vegas Golden Knights",WPG:"Winnipeg Jets",WSH:"Washington Capitals"};
const NBA_TEAMS={ATL:{name:"Atlanta Hawks",id:1610612737},BOS:{name:"Boston Celtics",id:1610612738},BKN:{name:"Brooklyn Nets",id:1610612751},CHA:{name:"Charlotte Hornets",id:1610612766},CHI:{name:"Chicago Bulls",id:1610612741},CLE:{name:"Cleveland Cavaliers",id:1610612739},DAL:{name:"Dallas Mavericks",id:1610612742},DEN:{name:"Denver Nuggets",id:1610612743},DET:{name:"Detroit Pistons",id:1610612765},GSW:{name:"Golden State Warriors",id:1610612744},HOU:{name:"Houston Rockets",id:1610612745},IND:{name:"Indiana Pacers",id:1610612754},LAC:{name:"LA Clippers",id:1610612746},LAL:{name:"Los Angeles Lakers",id:1610612747},MEM:{name:"Memphis Grizzlies",id:1610612763},MIA:{name:"Miami Heat",id:1610612748},MIL:{name:"Milwaukee Bucks",id:1610612749},MIN:{name:"Minnesota Timberwolves",id:1610612750},NOP:{name:"New Orleans Pelicans",id:1610612740},NYK:{name:"New York Knicks",id:1610612752},OKC:{name:"Oklahoma City Thunder",id:1610612760},ORL:{name:"Orlando Magic",id:1610612753},PHI:{name:"Philadelphia 76ers",id:1610612755},PHX:{name:"Phoenix Suns",id:1610612756},POR:{name:"Portland Trail Blazers",id:1610612757},SAC:{name:"Sacramento Kings",id:1610612758},SAS:{name:"San Antonio Spurs",id:1610612759},TOR:{name:"Toronto Raptors",id:1610612761},UTA:{name:"Utah Jazz",id:1610612762},WAS:{name:"Washington Wizards",id:1610612764}};
const NBA_ALIASES={NY:"NYK",NO:"NOP",SA:"SAS",UTAH:"UTA",WSH:"WAS",GS:"GSW"};
const NFL_TEAMS={ARI:"Arizona Cardinals",ATL:"Atlanta Falcons",BAL:"Baltimore Ravens",BUF:"Buffalo Bills",CAR:"Carolina Panthers",CHI:"Chicago Bears",CIN:"Cincinnati Bengals",CLE:"Cleveland Browns",DAL:"Dallas Cowboys",DEN:"Denver Broncos",DET:"Detroit Lions",GB:"Green Bay Packers",HOU:"Houston Texans",IND:"Indianapolis Colts",JAX:"Jacksonville Jaguars",KC:"Kansas City Chiefs",LV:"Las Vegas Raiders",LAC:"Los Angeles Chargers",LAR:"Los Angeles Rams",MIA:"Miami Dolphins",MIN:"Minnesota Vikings",NE:"New England Patriots",NO:"New Orleans Saints",NYG:"New York Giants",NYJ:"New York Jets",PHI:"Philadelphia Eagles",PIT:"Pittsburgh Steelers",SF:"San Francisco 49ers",SEA:"Seattle Seahawks",TB:"Tampa Bay Buccaneers",TEN:"Tennessee Titans",WSH:"Washington Commanders"};
const teamKey=value=>Array.from(String(value||"").normalize("NFD")).filter(ch=>ch.codePointAt(0)<768||ch.codePointAt(0)>879).join("").toLowerCase().replaceAll(".","").trim().split(" ").filter(Boolean).join(" ");
function teamInfo(raw,league=sport){
 const value=String(raw||""),code=value.toUpperCase();
 if(league==="nhl"){
  const found=NHL_TEAMS[code]?code:Object.keys(NHL_TEAMS).find(k=>teamKey(NHL_TEAMS[k])===teamKey(value));
  return found?{code:found,name:NHL_TEAMS[found],logo:"https://assets.nhle.com/logos/nhl/svg/"+found+"_light.svg"}:{code:"",name:value,logo:""};
 }
 if(league==="nba"){
  const resolved=NBA_ALIASES[code]||code;
  let found=NBA_TEAMS[resolved]?resolved:Object.keys(NBA_TEAMS).find(k=>teamKey(NBA_TEAMS[k].name)===teamKey(value));
  if(!found)found=Object.keys(NBA_TEAMS).find(k=>teamKey(NBA_TEAMS[k].name.replace("LA ","Los Angeles "))===teamKey(value));
  return found?{code:found,name:NBA_TEAMS[found].name,logo:"https://cdn.nba.com/logos/nba/"+NBA_TEAMS[found].id+"/global/L/logo.svg"}:{code:"",name:value,logo:""};
 }
 if(league==="nfl"){
  let found=NFL_TEAMS[code]?code:Object.keys(NFL_TEAMS).find(k=>teamKey(NFL_TEAMS[k])===teamKey(value));
  if(!found)found=Object.keys(NFL_TEAMS).find(k=>teamKey(NFL_TEAMS[k])===teamKey(value.replace("Las Vegas","Las Vegas")));
  return found?{code:found,name:NFL_TEAMS[found],logo:"https://a.espncdn.com/i/teamlogos/nfl/500/"+found.toLowerCase()+".png"}:{code:"",name:value,logo:""};
 }
 return {code:"",name:value,logo:""};
}
function appendTeam(row,raw,side,league,providedLogo){
 const info=teamInfo(raw,league),team=make("span",undefined,"daily-team daily-team-"+side);
 team.setAttribute("aria-label",info.name);
 const mark=make("span",undefined,"daily-team-logo");
 const initials=info.name.split(" ").filter(Boolean).map(x=>x[0]).slice(0,2).join("").toUpperCase();
 mark.append(make("span",initials,"daily-team-initials"));
 const source=providedLogo||info.logo;
 if(source&&/^https:\/\//i.test(source)){
  const img=document.createElement("img");img.src=source;img.alt="";img.loading="lazy";img.decoding="async";
  img.addEventListener("error",()=>img.remove(),{once:true});mark.append(img);
 }
 team.append(mark,make("span",info.name,"daily-team-name"));row.append(team);return info;
}
function matchState(g,options={}){
 const status=String(g.status||"").toUpperCase(),hasScore=g.away_score!=null&&g.home_score!=null;
 const supplied=options.stateText||"";
 if(hasScore){
  const label=g.completed||/final/i.test(supplied)?"Final":/en juego|intermedio|entretiempo/i.test(supplied)?"En juego":"";
  return String(g.away_score)+" : "+String(g.home_score)+(label?" · "+label:"");
 }
 if(supplied)return supplied;
 if(g.completed||["FINAL","OFF","STATUS_FINAL"].includes(status))return "Finalizado";
 return ({FUT:"Por comenzar",PRE:"Por comenzar",SCHEDULED:"Por comenzar",STATUS_SCHEDULED:"Por comenzar",LIVE:"En juego",CRIT:"En juego",STATUS_IN_PROGRESS:"En juego",STATUS_HALFTIME:"Entretiempo",STATUS_POSTPONED:"Aplazado",POSTPONED:"Aplazado",STATUS_CANCELED:"Cancelado",STATUS_DELAYED:"Demorado"}[status]||g.status||"Programado");
}
function makeMatchRow(g,options={}){
 const league=options.sport||g.sport||sport,row=make("article",undefined,"daily-match daily-match-card");
 row.dataset.sport=league;
 const away=appendTeam(row,g.away,"away",league,g.away_logo||g.awayLogo||g.away_badge);
 row.append(make("span","—","daily-match-versus"));
 const home=appendTeam(row,g.home,"home",league,g.home_logo||g.homeLogo||g.home_badge);
 const state=make("span",matchState(g,options),"daily-state");
 const text=state.textContent.toLowerCase();if(text.includes("en juego")||text.includes("entretiempo"))state.classList.add("is-live");if(text.includes("final")||g.completed)state.classList.add("is-final");
 row.append(state);
 if(league==="nhl"&&g.id!=null){row.dataset.nhlId=String(g.id).replace(/^nhl[-_:]/,"");row.dataset.home=away.code?teamInfo(g.home,league).code||String(g.home):String(g.home);row.dataset.away=away.code||String(g.away);}
 else if(league!=="nhl"&&text.includes("en juego")&&g.home_score==null&&g.away_score==null)row.append(make("small","Marcador en vivo no disponible; se conserva la última información del calendario.","live-note"));
 return row;
}
window.PulsoCalendar={makeMatchRow,teamInfo,matchState};
const localDay=()=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
const previousDay=d=>{const x=new Date(d+"T12:00:00Z");x.setUTCDate(x.getUTCDate()-1);return x.toISOString().slice(0,10);};
const dayOf=utc=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(utc));
const make=(tag,content,cls)=>{const el=document.createElement(tag);if(content!==undefined)el.textContent=content;if(cls)el.className=cls;return el;};
let snapshot=null,history=[],predictions=[],runtime={},feedFailure="",nhlCalendar=null;
function isGame(g){return g&&g.sport===sport&&g.id!=null&&g.start_utc&&g.home&&g.away;}
function result(g){if(!g.completed)return null;const a=Number(g.away_score),h=Number(g.home_score);if(g.home_score==null||g.away_score==null||!Number.isFinite(a)||!Number.isFinite(h))return null;return h>a?"home":h<a?"away":"draw";}
function checkPick(p,g){
 return String(p.game_id??p.event_id)===String(g.id)&&p.sport===g.sport&&p.market==="winner"&&["home","away","draw"].includes(p.pick)&&
 p.odds_used_in_model===false&&p.point_in_time_sources_verified===true&&
 Boolean(p.model_version)&&Number.isFinite(Date.parse(p.prediction_as_of_utc))&&
 Date.parse(p.prediction_as_of_utc)<Date.parse(g.start_utc);
}
function scored(){
 const map=new Map(history.filter(isGame).map(g=>[g.id+"",g])),seen=new Set(),out=[];
 for(const p of predictions){
  const id=String(p.game_id??p.event_id??"");const g=map.get(id);
  if(!g||!checkPick(p,g)||result(g)===null)continue;
  const key=id+":"+(p.market||"")+":"+p.model_version;
  if(seen.has(key))continue;seen.add(key);
  out.push({game:g,pick:p.pick,actual:result(g),won:p.pick===result(g)});
 }
 return out;
}
function stats(){
 const wins=scored().filter(x=>x.won).length,total=scored().length;
 const values=[total,total?((wins/total)*100).toFixed(1)+" %":"—",wins,total-wins];
 const labels=["PREDICCIONES TOTALES EVALUADAS","PORCENTAJE DE ACIERTO","GANADAS","PERDIDAS"];
 $("daily-stats").replaceChildren(...labels.map((label,i)=>{const card=make("article",undefined,"metric");card.append(make("span",label),make("strong",String(values[i])));return card;}));
 const date=previousDay($("daily-date").value);$("yesterday-label").textContent="Resultado de predicciones · "+date;
 const yesterday=scored().filter(x=>dayOf(x.game.start_utc)===date),root=$("yesterday-results");
 root.replaceChildren();
 if(!yesterday.length)root.append(make("p","No hay predicciones verificadas y resueltas del día anterior.","daily-empty"));
 for(const x of yesterday)root.append(make("div",x.game.away+" — "+x.game.home+" | "+(x.won?"✓ Ganada":"✕ Perdida")+" | Predicción: "+x.pick+" | Resultado: "+x.actual,"daily-match"));
}
function selectedSnapshot(){
 const date=$("daily-date").value;
 if(sport==="nhl"&&nhlCalendar?.included_dates?.includes(date))return nhlCalendar;
 return snapshot;
}
function selectedDateKnown(){const source=selectedSnapshot();return Boolean(source?.included_dates?.includes($("daily-date").value)||(source?.games||[]).some(g=>isGame(g)&&dayOf(g.start_utc)===$("daily-date").value));}
function activeGames(){return(selectedSnapshot()?.games||[]).filter(g=>isGame(g)&&dayOf(g.start_utc)===$("daily-date").value).sort((a,b)=>a.start_utc.localeCompare(b.start_utc));}
function nhlSummary(games){
 const root=$("nhl-day-summary");if(!root)return;
 const pending=games.filter(g=>!g.completed&&Date.parse(g.start_utc)>Date.now());
 root.replaceChildren(...[games.length+" en la jornada",pending.length+" por comenzar",games.filter(g=>["LIVE","CRIT","STATUS_IN_PROGRESS"].includes(g.status)).length+" en juego",games.filter(g=>g.completed).length+" finalizados"].map(text=>make("span",text,"nhl-summary-chip")));
 $("nhl-pending-summary").textContent=pending.length?pending.length+" encuentro"+(pending.length===1?"":"s")+" pendiente"+(pending.length===1?"":"s")+" de comenzar.":"No hay encuentros pendientes para esta fecha.";
}
function renderGames(){
 const games=activeGames(),root=$("daily-results"),source=selectedSnapshot(),known=selectedDateKnown();root.replaceChildren();
 $("daily-label").textContent=title+" · "+$("daily-date").value+" · "+games.length+" partidos";
 if(!games.length)root.append(make("p",known?"No hay partidos programados para esta fecha.":"El calendario de esta fecha aún no está publicado. Elige una fecha disponible.","daily-empty"));
 const grouped=new Map();
 for(const g of games){
  const country=sport==="soccer"?(g.country||"País no identificado"):null;
  const league=sport==="soccer"?(g.league||"Liga no identificada"):sport==="tennis"?(g.league||g.competition||"Circuito"):"Partidos";
  const key=sport==="soccer"?country+" / "+league:league;
  if(!grouped.has(key))grouped.set(key,[]);
  grouped.get(key).push(g);
 }
 for(const [group,items] of grouped){
  const sec=make("section",undefined,"daily-group");sec.append(make("h3",group));
  for(const g of items){
   const row=makeMatchRow(g);
   sec.append(row);
  }root.append(sec);
 }
 const errors=(source?.errors||[]).filter(x=>x.sport===sport);
 $("feed-message").textContent=source
 ? "Fuente: "+(source.source?source.source+" · ":"")+source.as_of_utc+(errors.length?" · "+errors.length+" errores en fuentes. Cobertura posiblemente incompleta.":" · Calendario obtenido de las fuentes configuradas.")
 : "No se pudo cargar el calendario. "+feedFailure;
 nhlSummary(games);renderSelection(games);stats();
 if(sport==="nhl"){
  const date=$("daily-date").value;
  $("run-simulation").disabled=!known||!games.some(g=>!g.completed&&Date.parse(g.start_utc)>Date.now());
  $("run-simulation").textContent="Ejecutar jornada · "+date;
  if(!known&&$("nhl-pending-summary"))$("nhl-pending-summary").textContent="Calendario no disponible para "+date+". No se puede ejecutar todavía.";
  if($("nhl-selected-date"))$("nhl-selected-date").textContent=new Date(date+"T12:00:00Z").toLocaleDateString("es-CL",{timeZone:"UTC",weekday:"long",day:"numeric",month:"long"});
  document.dispatchEvent(new CustomEvent("pulso:date-change",{detail:{date,known}}));
 }
}
function renderSelection(games){
 const root=$("simulation-games");root.replaceChildren();
 const radio=document.querySelector('input[name="simulation-scope"]:checked');
 $("simulation-selection").hidden=radio?.value!=="selected";
 for(const g of games){
  if(g.completed||Date.parse(g.start_utc)<=Date.now())continue;
  const label=make("label",undefined,"selection-item"),check=document.createElement("input");
  check.type="checkbox";check.value=String(g.id);check.name="chosen-game";
  label.append(check,make("span",g.away+" — "+g.home+(sport==="soccer"?" · "+(g.country||"")+" / "+(g.league||""):"")));
  root.append(label);
 }
 if(!root.children.length)root.append(make("p","No existen partidos pendientes de inicio para seleccionar.","daily-empty"));
}
async function runSimulation(){
 const candidates=activeGames().filter(g=>!g.completed&&Date.parse(g.start_utc)>Date.now());
 const scope=document.querySelector('input[name="simulation-scope"]:checked').value;
 const selected=new Set([...document.querySelectorAll('input[name="chosen-game"]:checked')].map(x=>x.value));
 const games=scope==="all"?candidates:candidates.filter(g=>selected.has(String(g.id)));
 const status=$("simulation-status");
 if(!games.length){status.textContent="Selecciona al menos un encuentro que aún no haya comenzado.";return;}
 if(sport==="nhl"&&scope!=="all"){status.textContent="El workflow NHL actual solo admite la jornada completa. Selecciona «Todos los partidos».";return;}
 if(!runtime.simulation_endpoint){status.textContent="Ejecución protegida aún no configurada. Utiliza el enlace a GitHub Actions en el panel NHL.";return;}
 const url=new URL(runtime.simulation_endpoint,location.href);
 const authorizedOrigin=runtime.simulation_endpoint_origin || location.origin;
 if(url.protocol!=="https:"||url.origin!==authorizedOrigin||url.pathname!=="/api/nhl/run"||url.username||url.password||url.search||url.hash||sport!=="nhl"){
  status.textContent="Endpoint de ejecución no autorizado.";return;
 }
 const today=localDay(),last=new Date(today+"T12:00:00Z");last.setUTCDate(last.getUTCDate()+7);
 if($("daily-date").value<today||$("daily-date").value>last.toISOString().slice(0,10)){
  status.textContent="Selecciona una fecha entre hoy y siete días más (hora de Santiago).";return;
 }
 const button=$("run-simulation");button.disabled=true;status.textContent="Solicitando ejecución protegida…";
 try{
  const response=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},credentials:"include",redirect:"error",
   body:JSON.stringify({sport,date:$("daily-date").value,scope,event_ids:games.map(g=>String(g.id))})});
  if(response.status===401||response.status===403)throw Error("Autenticación requerida o acceso denegado");
  if(!response.ok)throw Error("El servicio respondió HTTP "+response.status);
  if(!(response.headers.get("Content-Type")||"").includes("application/json"))throw Error("El servicio no devolvió una confirmación JSON");
  const data=await response.json();status.textContent=data.accepted?"Solicitud aceptada por GitHub Actions. Comprueba la ejecución en el enlace del panel NHL; todavía no hay resultado.":"No se confirmó la solicitud.";
 }catch(err){
  status.textContent="No se confirmó la ejecución. "+err.message+". Inicia sesión en Cloudflare Access y vuelve aquí. Si persiste, revisa CORS y cookies entre sitios. No reintentes automáticamente: comprueba primero GitHub Actions. ";
  const login=make("a","Iniciar sesión en Cloudflare Access");login.href=url.href;login.target="_blank";login.rel="noopener noreferrer";status.append(login);
 }finally{button.disabled=false;}
}
function nhlScheduleSnapshot(slate){
 if(sport!=="nhl"||slate?.kind!=="nhl_daily_complete_slate_274"||!Array.isArray(slate.games)||!slate.schedule_captured_at)return null;
 const games=slate.games.filter(g=>g.game_id&&g.home&&g.away&&Number.isFinite(Date.parse(g.start_utc))).map(g=>({
  id:String(g.game_id),sport:"nhl",home:g.home,away:g.away,start_utc:g.start_utc,
  completed:["OFF","FINAL"].includes(g.game_state_at_capture),status:g.game_state_at_capture||"Estado no disponible"
 }));
 return {games,as_of_utc:slate.schedule_captured_at,errors:[],source:"Calendario oficial NHL publicado"};
}
async function load(){
 $("daily-date").value=localDay();
 // NBA has a separate frozen-cohort source; do not load the legacy shared feed.
 if(sport==="nba")return;
 const entries=await Promise.allSettled(["./data/daily.json","./data/history.json","./data/predictions.json","./data/runtime-config.json","./data/nhl-complete-slate-latest.json","./data/nhl-schedule.json"].map(async path=>{
  const response=await fetch(path,{cache:"no-store"});if(!response.ok)throw Error(path+" "+response.status);return response.json();
 }));
 const got=i=>entries[i].status==="fulfilled"?entries[i].value:null;
 feedFailure=[0,...(sport==="nhl"?[4]:[])].map(i=>entries[i].status==="rejected"?entries[i].reason.message:"").filter(Boolean).join(" · ");
 nhlCalendar=got(5)?.kind==="nhl_calendar"&&Array.isArray(got(5).games)&&Array.isArray(got(5).included_dates)?got(5):null;
 snapshot=got(0)||nhlScheduleSnapshot(got(4));history=Array.isArray(got(1))?got(1):[];const p=got(2);
 predictions=Array.isArray(p)?p:Array.isArray(p?.predictions)?p.predictions:[];runtime=got(3)||{};
 renderGames();
}
function changeDate(){
 const date=$("daily-date").value;
 if(!/^20\d{2}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(Date.parse(date+"T12:00:00Z")))return;
 $("simulation-status").textContent="";if(sport!=="nba")renderGames();
}
$("daily-date").addEventListener("change",changeDate);
document.querySelectorAll('input[name="simulation-scope"]').forEach(r=>r.addEventListener("change",()=>renderSelection(activeGames())));
$("run-simulation").addEventListener("click",runSimulation);
$("crumb").textContent=title.toUpperCase();
$("sport-nav").append(make("div",title,"nav active"));
$("menu").addEventListener("click",()=>document.querySelector(".sidebar").classList.toggle("open"));
load();
