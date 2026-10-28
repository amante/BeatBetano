"use strict";
const $=id=>document.getElementById(id);
const SPORT={nba:"NBA",nfl:"NFL",nhl:"NHL",tennis:"Tenis",soccer:"Fútbol"};
let scoreboard=null,ledger=[];
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function chileDay(date){return new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(date);}
function yesterday(day){const d=new Date(day+"T12:00:00Z");d.setUTCDate(d.getUTCDate()-1);return d.toISOString().slice(0,10);}
function validScore(x){if(x===null||x===undefined||String(x).trim()==="")return null;const n=Number(x);return Number.isFinite(n)?n:null;}
function outcome(game){
 if(!game.completed)return null;
 const h=validScore(game.home_score),a=validScore(game.away_score);
 if(h===null||a===null)return null;
 return h>a?"home":a>h?"away":"draw";
}
function validatedPick(p,match){
 const gameId=String(p.event_id??p.game_id??"");
 const sport=String(p.sport||"");
 const asOf=Date.parse(p.prediction_as_of_utc||"");
 const start=Date.parse(match.start_utc||"");
 return gameId===String(match.id)&&sport===match.sport&&Number.isFinite(asOf)&&Number.isFinite(start)
   &&asOf<start&&p.odds_used_in_model===false&&p.point_in_time_sources_verified===true
   &&typeof p.model_version==="string"&&p.model_version.length>0
   &&["home","away","draw"].includes(p.pick)&&
   (sport==="soccer"||p.pick!=="draw");
}
function evaluate(games,predictions){
 const known=new Map(games.map(g=>[g.sport+":"+g.id,g]));
 const classified=[],seen=new Set();
 for(const pick of predictions){
  const key=pick.sport+":"+String(pick.event_id??pick.game_id)+":"+(pick.market||"winner")+":"+pick.model_version;
  if(seen.has(key))continue;seen.add(key);
  const game=known.get(pick.sport+":"+String(pick.event_id??pick.game_id));
  if(!game||!validatedPick(pick,game))continue;
  const actual=outcome(game);
  if(actual===null)continue;
  classified.push({sport:pick.sport,game,win:pick.pick===actual,model:pick.model_version,
    pick:pick.pick,actual});
 }
 return classified;
}
function card(label,value,detail){const outer=el("article",undefined,"metric"),l=el("span",label),v=el("strong",value),d=el("small",detail);outer.append(l,v,d);return outer;}
function draw(){
 const query=new URLSearchParams(location.search).get("sport");
 const sport=SPORT[query]?query:"nba";
 const date=$("daily-date").value;
 const all=(scoreboard?.games||[]).filter(g=>g.sport===sport&&chileDay(new Date(g.start_utc))===date);
 const yesterdayDate=yesterday(date);
 const previous=(scoreboard?.games||[]).filter(g=>g.sport===sport&&chileDay(new Date(g.start_utc))===yesterdayDate);
 // No guessing: historical stats require actual archived final outcomes.
 const allResults=evaluate(scoreboard?.games||[],ledger).filter(x=>x.sport===sport);
 const wins=allResults.filter(x=>x.win).length,losses=allResults.length-wins;
 const relevant=allResults.filter(x=>chileDay(new Date(x.game.start_utc))===yesterdayDate);
 const stats=$("daily-stats");stats.replaceChildren(
  card("PREDICCIONES EVALUADAS",String(allResults.length),"Solo picks congelados, verificados y finalizados"),
  card("PORCENTAJE DE ACIERTO",allResults.length?(100*wins/allResults.length).toFixed(1)+" %":"—","No se cuentan partidos sin liquidar"),
  card("GANADAS",String(wins),"Predicción coincidente con ganador"),
  card("PERDIDAS",String(losses),"Predicción distinta del resultado"));
 const body=$("daily-results");body.replaceChildren();
 const grouped= new Map();
 for(const g of all){
  const grouping=sport==="soccer"?[g.country||"Otros",g.league||"Sin liga"]:sport==="tennis"?[g.league||g.competition||"Circuito"]:[];
  const key=grouping.join(" / ")||"Partidos de hoy";
  if(!grouped.has(key))grouped.set(key,[]);
  grouped.get(key).push(g);
 }
 if(!all.length){body.append(el("p",scoreboard?.errors?.length?"No hay partidos confirmados en las fuentes disponibles; consulta los errores de cobertura.":"No hay partidos en el snapshot para esta fecha.","daily-empty"));}
 for(const [name,games] of grouped){
  const section=el("section",undefined,"daily-group");
  section.append(el("h3",name));
  for(const g of games){
   const row=el("div",undefined,"daily-match");
   const time=el("span",new Date(g.start_utc).toLocaleTimeString("es-CL",{timeZone:"America/Santiago",hour:"2-digit",minute:"2-digit"}),"daily-time");
   const names=el("strong",g.away+" — "+g.home);
   const state=el("span",g.completed?(g.away_score??"—")+" : "+(g.home_score??"—"):g.status,"daily-state");
   row.append(time,names,state);section.append(row);
  }body.append(section);
 }
 $("daily-label").textContent=SPORT[sport]+" · "+date+" · "+all.length+" partidos";
 $("yesterday-label").textContent="Resultados de predicciones · "+yesterdayDate;
 const prev=$("yesterday-results");prev.replaceChildren();
 if(!relevant.length)prev.append(el("p","Sin predicciones verificadas y liquidadas del día anterior.","daily-empty"));
 for(const item of relevant){prev.append(el("div",item.game.away+" — "+item.game.home+" · "+(item.win?"✓ Ganada":"✕ Perdida")+" · Pronóstico: "+item.pick+" · Resultado: "+item.actual,"daily-match"));}
 const errorSports=(scoreboard?.errors||[]).filter(e=>e.sport===sport);
 $("feed-message").textContent=scoreboard
  ? "Fuente: "+scoreboard.as_of_utc+" · "+(errorSports.length?errorSports.length+" errores de cobertura; listado posiblemente incompleto.":"Cobertura de fuentes consultadas.")+" Las métricas requieren predicciones históricas verificadas."
  : "No existe un snapshot diario cargado. Ejecuta el recolector o importa un reporte.";
}
async function load(){
 try{
  const r=await fetch("./data/daily.json?fresh="+Date.now(),{cache:"no-store"});
  if(r.ok){const data=await r.json();if(!Array.isArray(data.games))throw Error("Snapshot inválido");scoreboard=data;
   if(/^\d{4}-\d{2}-\d{2}$/.test(data.date))$("daily-date").value=data.date;}
 }catch(err){$("feed-message").textContent="Sin conexión con el snapshot de partidos: "+err.message;}
 try{const r=await fetch("./data/predictions.json",{cache:"no-store"});if(r.ok){const d=await r.json();ledger=Array.isArray(d)?d:Array.isArray(d.predictions)?d.predictions:[];}}catch(_){}
 draw();
}
$("daily-date").addEventListener("change",draw);
$("predictions-file").addEventListener("change",async e=>{
 try{const f=e.target.files[0];if(!f)return;if(f.size>5e6)throw Error("Archivo mayor de 5MB");
 const parsed=JSON.parse(await f.text());const rows=Array.isArray(parsed)?parsed:parsed.predictions;
 if(!Array.isArray(rows))throw Error("Se requiere predictions[]");ledger=rows;draw();
 }catch(err){$("feed-message").textContent="Error importando pronósticos: "+err.message;}
 e.target.value="";
});
load();
