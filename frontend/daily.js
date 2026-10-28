"use strict";
const $=id=>document.getElementById(id);
const SPORTS={nba:"NBA",nfl:"NFL",nhl:"NHL",soccer:"Fútbol",tennis:"Tenis"};
const qs=new URLSearchParams(location.search),sport=qs.get("sport");
if(!Object.hasOwn(SPORTS,sport)){location.replace("./index.html");throw Error("Seleccione una disciplina desde la portada");}
const title=SPORTS[sport];
const localDay=()=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
const previousDay=d=>{const x=new Date(d+"T12:00:00Z");x.setUTCDate(x.getUTCDate()-1);return x.toISOString().slice(0,10);};
const dayOf=utc=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(utc));
const make=(tag,content,cls)=>{const el=document.createElement(tag);if(content!==undefined)el.textContent=content;if(cls)el.className=cls;return el;};
let snapshot=null,history=[],predictions=[],runtime={};
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
function activeGames(){return(snapshot?.games||[]).filter(g=>isGame(g)&&dayOf(g.start_utc)===$("daily-date").value).sort((a,b)=>a.start_utc.localeCompare(b.start_utc));}
function renderGames(){
 const games=activeGames(),root=$("daily-results");root.replaceChildren();
 $("daily-label").textContent=title+" · "+$("daily-date").value+" · "+games.length+" partidos";
 if(!games.length)root.append(make("p",snapshot?"Sin partidos confirmados para esta disciplina y fecha.":"No hay calendario disponible; pendiente actualización de las fuentes.","daily-empty"));
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
   const row=make("div",undefined,"daily-match");
   row.append(make("span",new Date(g.start_utc).toLocaleTimeString("es-CL",{timeZone:"America/Santiago",hour:"2-digit",minute:"2-digit"}),"daily-time"),
     make("strong",g.away+" — "+g.home),make("span",g.completed?String(g.away_score??"—")+" : "+String(g.home_score??"—"):g.status||"Programado","daily-state"));
   sec.append(row);
  }root.append(sec);
 }
 const errors=(snapshot?.errors||[]).filter(x=>x.sport===sport);
 $("feed-message").textContent=snapshot
 ? "Fuente: "+snapshot.as_of_utc+(errors.length?" · "+errors.length+" errores en fuentes. Cobertura posiblemente incompleta.":" · Calendario obtenido de las fuentes configuradas.")
 : "No se dispone de una publicación de calendario. El sistema no acepta cargas manuales.";
 renderSelection(games);stats();
}
function renderSelection(games){
 const root=$("simulation-games");root.replaceChildren();
 const radio=document.querySelector('input[name="simulation-scope"]:checked');
 $("simulation-selection").hidden=radio?.value!=="selected";
 for(const g of games){
  if(g.completed)continue;
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
 if(!runtime.simulation_endpoint){status.textContent="Simulación pendiente: el backend de ejecución aún no está conectado. No se ejecutó ningún modelo.";return;}
 const url=new URL(runtime.simulation_endpoint,location.href);
 if(url.origin!==location.origin||url.protocol!=="https:"){status.textContent="Endpoint no autorizado: debe ser HTTPS y del mismo origen.";return;}
 const button=$("run-simulation");button.disabled=true;status.textContent="Enviando solicitud de simulación…";
 try{
  const response=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",
   body:JSON.stringify({sport,date:$("daily-date").value,scope,event_ids:games.map(g=>String(g.id))})});
  if(!response.ok)throw Error("HTTP "+response.status);
  const data=await response.json();status.textContent=data.job_id?"Simulación solicitada. Trabajo: "+data.job_id:"Solicitud recibida; espera la confirmación del motor.";
 }catch(err){status.textContent="No se pudo ejecutar: "+err.message;}finally{button.disabled=false;}
}
async function load(){
 $("daily-date").value=localDay();
 const entries=await Promise.allSettled(["./data/daily.json","./data/history.json","./data/predictions.json","./data/runtime-config.json"].map(async path=>{
  const response=await fetch(path,{cache:"no-store"});if(!response.ok)throw Error(path+" "+response.status);return response.json();
 }));
 const got=i=>entries[i].status==="fulfilled"?entries[i].value:null;
 snapshot=got(0);history=Array.isArray(got(1))?got(1):[];const p=got(2);
 predictions=Array.isArray(p)?p:Array.isArray(p?.predictions)?p.predictions:[];runtime=got(3)||{};
 renderGames();
}
$("daily-date").addEventListener("change",renderGames);
document.querySelectorAll('input[name="simulation-scope"]').forEach(r=>r.addEventListener("change",()=>renderSelection(activeGames())));
$("run-simulation").addEventListener("click",runSimulation);
$("crumb").textContent=title.toUpperCase();
$("sport-nav").append(make("div",title,"nav active"));
$("menu").addEventListener("click",()=>document.querySelector(".sidebar").classList.toggle("open"));
load();
