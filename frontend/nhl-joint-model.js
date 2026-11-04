"use strict";
(function(scope){
 const finite=x=>typeof x==="number"&&Number.isFinite(x);
 const inRange=x=>finite(x)&&x>=0&&x<=1;
 const sumToOne=xs=>xs.every(inRange)&&Math.abs(xs.reduce((a,b)=>a+b,0)-1)<1e-5;
 const dayOf=utc=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(utc));
 function validate(data){
  if(!data||data.kind!=="nhl_joint_match_daily_runs_v322"||data.official!==false||data.calibrated!==false||data.odds_used!==false||data.public_base_replaced!==false||!Array.isArray(data.games)||!Array.isArray(data.blocked_games))return false;
  if(data.date!==null&&!/^\d{4}-\d{2}-\d{2}$/.test(data.date))return false;
  if(data.date!==null&&(!Number.isFinite(Date.parse(data.generated_at_utc))||!Number.isFinite(Date.parse(data.published_at_utc))))return false;
  const seen=new Set();
  for(const game of data.games){
   const id=String(game&&game.game_id||"");
   if(!id||seen.has(id)||!game.home||!game.away||!Number.isFinite(Date.parse(game.start_utc))||!Number.isFinite(Date.parse(game.captured_at_utc))||Date.parse(game.captured_at_utc)>=Date.parse(game.start_utc)||game.status!=="conditional_unvalidated_scenarios"||game.publishable!==false||game.calibrated!==false||!Array.isArray(game.scenarios)||game.scenario_count!==game.scenarios.length||!game.scenario_count)return false;
   seen.add(id);
   for(const scenario of game.scenarios){
    if(!scenario.home_goalie||!scenario.away_goalie||!scenario.home_goalie.name||!scenario.away_goalie.name||!finite(scenario.expected_goals&&scenario.expected_goals.home)||scenario.expected_goals.home<=0||!finite(scenario.expected_goals&&scenario.expected_goals.away)||scenario.expected_goals.away<=0)return false;
    if(scenario.scenario_weight!==null&&scenario.scenario_weight!==undefined&&!inRange(scenario.scenario_weight))return false;
    for(const goalie of [scenario.home_goalie,scenario.away_goalie])if(goalie.starter_probability!==null&&goalie.starter_probability!==undefined&&!inRange(goalie.starter_probability))return false;
    const m=scenario.markets;
    if(!m||!sumToOne([m.illustrative_ml&&m.illustrative_ml.home,m.illustrative_ml&&m.illustrative_ml.away])||!sumToOne([m.regulation&&m.regulation.home,m.regulation&&m.regulation.draw,m.regulation&&m.regulation.away])||!inRange(m.three_goal_lead&&m.three_goal_lead.home)||!inRange(m.three_goal_lead&&m.three_goal_lead.away)||!inRange(m.first_to_three_goal_lead&&m.first_to_three_goal_lead.home)||!inRange(m.first_to_three_goal_lead&&m.first_to_three_goal_lead.away)||m.first_to_three_goal_lead.home+m.first_to_three_goal_lead.away>1.00001)return false;
   }
  }
  return data.blocked_games.every(x=>x&&x.game_id&&x.home&&x.away&&typeof x.reason==="string");
 }
 function weighted(game){
  const scenarios=game&&game.scenarios;if(!Array.isArray(scenarios)||!scenarios.length)return null;
  const weights=scenarios.map(s=>s.scenario_weight);
  if(!sumToOne(weights))return null;
  const avg=(selector)=>scenarios.reduce((sum,s,i)=>sum+weights[i]*selector(s),0);
  const keys=["regulation","illustrative_ml","three_goal_lead","first_to_three_goal_lead"],markets={};
  for(const key of keys){const first=scenarios[0].markets[key];markets[key]={};for(const outcome of Object.keys(first))markets[key][outcome]=avg(s=>s.markets[key][outcome]);}
  return {expected_goals:{home:avg(s=>s.expected_goals.home),away:avg(s=>s.expected_goals.away)},markets};
 }
 function selectDate(data,date){if(!validate(data)||!date||date!==data.date)return null;return data.games.filter(g=>dayOf(g.start_utc)===date);}
 if(typeof module==="object"&&module.exports)module.exports={validate,selectDate,dayOf,weighted};
 const doc=scope.document;if(!doc)return;
 const root=doc.getElementById("nhl-joint-model");if(!root||new URLSearchParams(scope.location.search).get("sport")!=="nhl")return;
 const make=(tag,text,cls)=>{const el=doc.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
 const pct=x=>inRange(x)?(x*100).toFixed(1).replace(".",",")+"%":"—";
 let feed=null,error=null,dateInput=doc.getElementById("daily-date");
 function addScenario(game,scenario,index){
  const card=make("article",undefined,"nhl-joint-scenario"),goalie=(g)=>g.name+(inRange(g.starter_probability)?" · titularidad histórica "+pct(g.starter_probability):g.starter_confirmed?" · confirmado":" · candidato");
  card.append(make("h5","Escenario "+(index+1)+" · Local: "+goalie(scenario.home_goalie)+" · Visita: "+goalie(scenario.away_goalie)));
  card.append(make("p","Goles esperados · "+game.home+" "+scenario.expected_goals.home.toFixed(2)+" — "+scenario.expected_goals.away.toFixed(2)+" "+game.away,"nhl-joint-goals"));
  const m=scenario.markets,none=Math.max(0,1-m.first_to_three_goal_lead.home-m.first_to_three_goal_lead.away),grid=make("div",undefined,"nhl-joint-market-grid");
  const rows=[["Ganador ilustrativo",game.home+" "+pct(m.illustrative_ml.home),game.away+" "+pct(m.illustrative_ml.away)],["Tiempo regular",game.home+" "+pct(m.regulation.home),"Empate "+pct(m.regulation.draw)+" · "+game.away+" "+pct(m.regulation.away)],["Alcanza ventaja de +3",game.home+" "+pct(m.three_goal_lead.home),game.away+" "+pct(m.three_goal_lead.away)],["Primero en +3",game.home+" "+pct(m.first_to_three_goal_lead.home),game.away+" "+pct(m.first_to_three_goal_lead.away)+" · Ninguno "+pct(none)]];
  rows.forEach(row=>{const item=make("div",undefined,"nhl-joint-market");item.append(make("strong",row[0]),make("span",row[1]),make("span",row[2]));grid.append(item);});card.append(grid);return card;
 }
 function render(){
  root.replaceChildren(make("h3","Modelo integrado NHL · escenarios"));const meta=make("div",undefined,"nhl-joint-meta");meta.append(make("span","Experimental · no calibrado","nhl-experimental-badge"));root.append(meta);
  root.append(make("p","Alineaciones y minutos EV/PP/PK, producción proyectada de jugadores, bajas identificadas, rendimiento PP/PK, defensa por tiros y arqueros candidatos modifican estos escenarios. Cada combinación de arqueros se muestra por separado. No reemplaza el baseline de PULSO.","nhl-joint-note"));
  const status=make("p","Consultando última ejecución…","daily-source");root.append(status);
  if(!feed){status.textContent=error?"No se pudo cargar el modelo integrado: "+error:"El primer escenario aparecerá después de la próxima ejecución diaria.";return;}
  if(!validate(feed)){status.textContent="La publicación integrada no superó la validación. No se muestran sus probabilidades.";return;}
  if(!feed.date){status.textContent="Aún no hay una ejecución diaria publicada.";return;}
  const date=dateInput&&dateInput.value||feed.date;
  status.textContent="Última captura: "+feed.date+" · "+feed.games.length+" partidos con escenarios · "+feed.blocked_games.length+" bloqueados · publicada "+new Date(feed.published_at_utc).toLocaleString("es-CL",{timeZone:"America/Santiago",dateStyle:"short",timeStyle:"short"})+" (Chile)";
  if(date!==feed.date){root.append(make("p","No hay escenarios publicados para "+date+". La última captura es del "+feed.date+". No mostramos datos de otra fecha.","daily-empty"));return;}
  if(!feed.games.length&&!feed.blocked_games.length)root.append(make("p","La captura no encontró partidos elegibles para esta fecha.","daily-empty"));
  feed.games.forEach(game=>{const match=make("section",undefined,"nhl-joint-game");match.append(make("h4",game.away+" @ "+game.home));match.append(make("p",new Date(game.start_utc).toLocaleString("es-CL",{timeZone:"America/Santiago",dateStyle:"medium",timeStyle:"short"})+" · "+game.scenario_count+" combinaciones de arqueros","nhl-joint-kicker"));const mix=weighted(game);if(mix){const card=make("article",undefined,"nhl-joint-scenario");card.append(make("h5","Estimación combinada · titularidades históricas"));card.append(make("p","Goles esperados · "+game.home+" "+mix.expected_goals.home.toFixed(2)+" — "+mix.expected_goals.away.toFixed(2)+" "+game.away,"nhl-joint-goals"));const m=mix.markets;card.append(make("p","Ganador ilustrativo · "+game.home+" "+pct(m.illustrative_ml.home)+" · "+game.away+" "+pct(m.illustrative_ml.away)));card.append(make("p","Tiempo regular · "+game.home+" "+pct(m.regulation.home)+" · Empate "+pct(m.regulation.draw)+" · "+game.away+" "+pct(m.regulation.away)));card.append(make("p","Alcanza ventaja de +3 · "+game.home+" "+pct(m.three_goal_lead.home)+" · "+game.away+" "+pct(m.three_goal_lead.away)));card.append(make("p","Primero en +3 · "+game.home+" "+pct(m.first_to_three_goal_lead.home)+" · "+game.away+" "+pct(m.first_to_three_goal_lead.away)));match.append(card);}else{match.append(make("p","Sin estimación combinada: las titularidades históricas no cubren todos los partidos previos del equipo.","nhl-joint-footnote"));}game.scenarios.forEach((s,i)=>match.append(addScenario(game,s,i)));root.append(match);});
  if(feed.blocked_games.length){const details=make("details",undefined,"nhl-joint-blocked");details.append(make("summary",feed.blocked_games.length+" partidos sin escenario por falta o ambigüedad de fuentes"));feed.blocked_games.forEach(g=>details.append(make("p",g.away+" @ "+g.home+" · "+g.reason)));root.append(details);}
  root.append(make("p","La estimación combinada usa la proporción de partidos iniciados por cada candidato en la temporada actual. Solo aparece si el historial de candidatos cubre todos los partidos previos del equipo. Es una frecuencia descriptiva sin calibración; el modelo sigue siendo experimental y no oficial.","nhl-joint-footnote"));
 }
 doc.addEventListener("pulso:date-change",render);if(dateInput)dateInput.addEventListener("change",render);render();
 fetch("./data/nhl-joint-model-latest.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();}).then(data=>{if(!validate(data))throw new Error("formato no válido");feed=data;error=null;render();}).catch(e=>{error=e.message;render();});
})(typeof window!=="undefined"?window:globalThis);
