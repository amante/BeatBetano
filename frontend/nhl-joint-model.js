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
    if(m.comeback_after_two_goal_deficit&&(!inRange(m.comeback_after_two_goal_deficit.home)||!inRange(m.comeback_after_two_goal_deficit.away)))return false;
    if(m.strong_win_regulation&&(!inRange(m.strong_win_regulation.home)||!inRange(m.strong_win_regulation.away)||m.strong_win_regulation.home+m.strong_win_regulation.away>1.00001))return false;
    if(m.double_chance_regulation&&(!inRange(m.double_chance_regulation.home)||!inRange(m.double_chance_regulation.away)))return false;
    if(scenario.player_probabilities!==undefined){
     for(const players of Object.values(scenario.player_probabilities)){
      if(!Array.isArray(players)||players.some(p=>!p||!p.player_id||!p.name||!p.expected||!p.probability||
       !finite(p.expected.goals)||p.expected.goals<0||
       (p.expected.assists!==null&&p.expected.assists!==undefined&&(!finite(p.expected.assists)||p.expected.assists<0))||
       (p.expected.points!==null&&p.expected.points!==undefined&&(!finite(p.expected.points)||p.expected.points<0))||
       !inRange(p.probability.goal_at_least_one)||
       (p.probability.assist_at_least_one!==null&&p.probability.assist_at_least_one!==undefined&&!inRange(p.probability.assist_at_least_one))||
       (p.probability.point_at_least_one!==null&&p.probability.point_at_least_one!==undefined&&!inRange(p.probability.point_at_least_one))||
       (p.probability.point_two_or_more!==null&&p.probability.point_two_or_more!==undefined&&!inRange(p.probability.point_two_or_more))))return false;
     }
    }
   }
  }
  return data.blocked_games.every(x=>x&&x.game_id&&x.home&&x.away&&typeof x.reason==="string"&&(!x.category||["lineup_not_confirmed","other_input_unavailable"].includes(x.category)));
 }
 function weighted(game){
  const scenarios=game&&game.scenarios;if(!Array.isArray(scenarios)||!scenarios.length)return null;
  const weights=scenarios.map(s=>s.scenario_weight);
  if(!sumToOne(weights))return null;
  const avg=(selector)=>scenarios.reduce((sum,s,i)=>sum+weights[i]*selector(s),0);
  const keys=["regulation","illustrative_ml","three_goal_lead","first_to_three_goal_lead"];
  if(scenarios.every(s=>s.markets.comeback_after_two_goal_deficit))keys.push("comeback_after_two_goal_deficit");
  if(scenarios.every(s=>s.markets.strong_win_regulation))keys.push("strong_win_regulation");
  if(scenarios.every(s=>s.markets.double_chance_regulation))keys.push("double_chance_regulation");
  const markets={};
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
 let rotowireFeed=null;
 function rotowirePlayerText(player){
  if(!player||!player.name)return "";
  const identity=player.player_id?"ID NHL "+player.player_id:"identidad pendiente";
  const status=player.reported_status?" · "+player.reported_status:"";
  return player.name+" · "+identity+status;
 }
 function rotowireSectionText(section){
  if(!section||!Array.isArray(section.players)||!section.players.length)return "Sin nombres identificados";
  return section.players.map(rotowirePlayerText).join(" · ");
 }
 function addRotowireEvidence(parent,game){
  const embedded=game&&game.rotowire_pregame;
  const record=embedded?{
   game_id:game.game_id,home:game.home,away:game.away,status:embedded.status,
   teams:embedded.teams,market_observation:embedded.market_observation,source:embedded.source
  }:(rotowireFeed&&Array.isArray(rotowireFeed.games)?rotowireFeed.games.find(x=>String(x.game_id)===String(game.game_id)):null);
  if(!record)return;
  const details=make("details",undefined,"nhl-joint-context");
  details.append(make("summary","RotoWire · evidencia pregame"));
  if(record.status!=="observed"){
   details.append(make("p","Captura RotoWire no disponible para este partido."));
   if(record.source_error||record.reason)details.append(make("small",record.source_error||record.reason));
   parent.append(details);return;
  }
  for(const team of [record.home,record.away]){
   const evidence=record.teams&&record.teams[team];
   if(!evidence)continue;
   details.append(make("strong",team));
   details.append(make("p","Portero · "+(evidence.goalie?rotowirePlayerText({...evidence.goalie,reported_status:evidence.goalie.reported_status}):"sin identificación")));
   details.append(make("p","PP1 · "+rotowireSectionText(evidence.power_play_1)));
   details.append(make("p","PP2 · "+rotowireSectionText(evidence.power_play_2)));
   details.append(make("p","Lesiones · "+rotowireSectionText(evidence.injuries)));
  }
  const market=record.market_observation||{};
  const ml=market.moneyline||{},total=market.total_goals||{};
  details.append(make("p","Mercado RotoWire · ML "+(ml.raw||"s/d")+" · Total "+(total.line??"s/d")));
  details.append(make("small","Capturado "+(record.source&&record.source.captured_at_utc||rotowireFeed.captured_at_utc||"s/d")+" · Las cuotas son informativas. PP1/PP2 solo entra al cálculo si ambas unidades y sus jugadores quedan identificados y tienen historial."));
  parent.append(details);
 }
 function addRotowirePPAudit(parent,game){
  const distribution=game&&game.minute_distribution||{};
  const teams=[game.home,game.away];
  const rows=teams.map(team=>({team,audit:distribution[team]&&distribution[team].rotowire_power_play}));
  if(!rows.some(x=>x.audit))return;
  const details=make("details",undefined,"nhl-joint-context");
  const applied=rows.filter(x=>x.audit&&x.audit.applied).length;
  details.append(make("summary",applied?"PP1/PP2 · ajuste aplicado a "+applied+" equipo"+(applied===1?"":"s"):"PP1/PP2 · sin ajuste por evidencia incompleta"));
  const reasons={
   rotowire_observation_unavailable:"captura RotoWire no disponible",
   power_play_1_not_observed:"unidad PP1 no observada",
   power_play_2_not_observed:"unidad PP2 no observada",
   power_play_1_does_not_have_five_resolved_players:"PP1 no tiene cinco jugadores identificados",
   power_play_2_does_not_have_five_resolved_players:"PP2 no tiene cinco jugadores identificados",
   power_play_1_contains_unresolved_player_identity:"faltan identidades confirmadas en PP1",
   power_play_2_contains_unresolved_player_identity:"faltan identidades confirmadas en PP2",
   player_appears_in_both_power_play_units:"un jugador aparece en ambas unidades",
   no_projected_team_power_play_minutes:"sin minutos PP proyectados",
   no_historical_PP_minutes_for_RotoWire_units:"historial de minutos PP insuficiente",
   historical_PP_minutes_cannot_allocate_full_budget:"no se pudo distribuir el presupuesto PP",
   could_not_conserve_projected_power_play_minutes:"no se pudo conservar el total de minutos PP",
   projected_power_play_budget_exceeds_unit_capacity:"la capacidad de minutos de las unidades no alcanza"
  };
  for(const row of rows){
   const audit=row.audit;if(!audit)continue;
   if(audit.applied){
    const delta=finite(audit.projected_PP_goal_delta)?(audit.projected_PP_goal_delta>0?"+":"")+audit.projected_PP_goal_delta.toFixed(3).replace(".",","):"—";
    details.append(make("p",row.team+" · "+audit.team_PP_minutes_before?.toFixed(1)+" min PP conservados · goles PP estimados "+audit.projected_PP_goals_before?.toFixed(3)+" → "+audit.projected_PP_goals_after?.toFixed(3)+" · Δ "+delta+" goles"));
    for(const key of ["PP1","PP2"]){const unit=audit.units&&audit.units[key];if(Array.isArray(unit))details.append(make("small",key+" · "+unit.map(p=>p.name+" ("+(p.projected_PP_minutes||0).toFixed(1)+" min)").join(" · ")));}
   }else details.append(make("p",row.team+" · sin ajuste: "+(reasons[audit.reason]||audit.reason||"evidencia insuficiente")));
  }
  details.append(make("small","Reasigna el presupuesto PP existente según el tiempo histórico en PP; no crea minutos ni confirma las alineaciones. Escenario experimental, sin calibración."));
  parent.append(details);
 }
 function ppImpactText(impact,game){
  if(!impact||impact.status!=="applied_unvalidated_scenario_delta")return null;
  const delta=impact.market_probability_delta||{},ml=delta.illustrative_ml||{};
  const pp=x=>finite(x)?(x>0?"+":"")+(x*100).toFixed(2).replace(".",",")+" pp":"—";
  const goals=[];
  for(const code of [game.home,game.away]){
   const before=impact[code===game.home?"home_expected_goals_without_PP1_PP2":"away_expected_goals_without_PP1_PP2"];
   const after=code===game.home?impact.current_home_expected_goals:impact.current_away_expected_goals;
   if(finite(before)&&finite(after))goals.push(code+" Δ "+(after-before>0?"+":"")+(after-before).toFixed(3).replace(".",",")+" goles");
  }
  return "Efecto PP1/PP2 vs cálculo base · ML "+game.home+" "+pp(ml.home)+" · "+game.away+" "+pp(ml.away)+(goals.length?" · "+goals.join(" · "):"")+" · experimental";
 }
 function weightedPPImpactText(game){
  const scenarios=game&&game.scenarios;
  if(!Array.isArray(scenarios)||!scenarios.length)return null;
  const impacts=scenarios.map(s=>s.rotowire_pp_impact);
  const weights=scenarios.map(s=>s.scenario_weight);
  if(impacts.some(x=>!x||x.status!=="applied_unvalidated_scenario_delta")||!sumToOne(weights))return null;
  const avg=selector=>impacts.reduce((sum,item,i)=>sum+weights[i]*selector(item),0);
  const mlHome=avg(x=>x.market_probability_delta?.illustrative_ml?.home);
  const mlAway=avg(x=>x.market_probability_delta?.illustrative_ml?.away);
  const homeGoals=avg(x=>x.current_home_expected_goals-x.home_expected_goals_without_PP1_PP2);
  const awayGoals=avg(x=>x.current_away_expected_goals-x.away_expected_goals_without_PP1_PP2);
  const pp=x=>finite(x)?(x>0?"+":"")+(x*100).toFixed(2).replace(".",",")+" pp":"—";
  const g=x=>finite(x)?(x>0?"+":"")+x.toFixed(3).replace(".",","):"—";
  return "Efecto PP1/PP2 ponderado vs base · "+game.home+" "+pp(mlHome)+" ML, "+g(homeGoals)+" goles · "+game.away+" "+pp(mlAway)+" ML, "+g(awayGoals)+" goles · escenario experimental";
 }
 function addPlayerProbabilities(parent,team,players){
  if(!Array.isArray(players)||!players.length)return;
  const details=make("details",undefined,"nhl-joint-player-props");
  details.append(make("summary",team+" · probabilidades individuales ("+players.length+")"));
  const list=make("div",undefined,"nhl-joint-player-list");
  for(const player of players){
   const row=make("article",undefined,"nhl-joint-player-row");
   row.append(make("strong",player.name));
   const p=player.probability||{};
   row.append(make("span","Gol ≥1 "+pct(p.goal_at_least_one)+" · Asistencia ≥1 "+pct(p.assist_at_least_one)+" · Punto ≥1 "+pct(p.point_at_least_one)+" · 2+ puntos "+pct(p.point_two_or_more)));
   row.append(make("small","Proyección: "+(player.expected.goals??0).toFixed(2)+" G + "+(player.expected.assists==null?"s/d":player.expected.assists.toFixed(2)+" A")+" = "+(player.expected.points==null?"s/d":player.expected.points.toFixed(2)+" P")+" · escenario experimental, sin calibrar"));
   list.append(row);
  }
  details.append(list);parent.append(details);
 }
 function addScenario(game,scenario,index){
  const card=make("article",undefined,"nhl-joint-scenario"),goalie=(g)=>g.name+(inRange(g.starter_probability)?" · titularidad histórica "+pct(g.starter_probability):g.starter_confirmed?" · confirmado":" · candidato");
  card.append(make("h5","Escenario "+(index+1)+" · Local: "+goalie(scenario.home_goalie)+" · Visita: "+goalie(scenario.away_goalie)));
  card.append(make("p","Goles esperados · "+game.home+" "+scenario.expected_goals.home.toFixed(2)+" — "+scenario.expected_goals.away.toFixed(2)+" "+game.away,"nhl-joint-goals"));const ppText=ppImpactText(scenario.rotowire_pp_impact,game);if(ppText)card.append(make("p",ppText,"nhl-joint-footnote"));
  const m=scenario.markets,none=Math.max(0,1-m.first_to_three_goal_lead.home-m.first_to_three_goal_lead.away),grid=make("div",undefined,"nhl-joint-market-grid");
  const rows=[["Ganador ilustrativo",game.home+" "+pct(m.illustrative_ml.home),game.away+" "+pct(m.illustrative_ml.away)],["Tiempo regular",game.home+" "+pct(m.regulation.home),"Empate "+pct(m.regulation.draw)+" · "+game.away+" "+pct(m.regulation.away)],["Alcanza ventaja de +3",game.home+" "+pct(m.three_goal_lead.home),game.away+" "+pct(m.three_goal_lead.away)],["Primero en +3",game.home+" "+pct(m.first_to_three_goal_lead.home),game.away+" "+pct(m.first_to_three_goal_lead.away)+" · Ninguno "+pct(none)]];
  if(m.strong_win_regulation)rows.push(["FUERTE · gana por 2+ (60 min)",game.home+" "+pct(m.strong_win_regulation.home),game.away+" "+pct(m.strong_win_regulation.away)]);
  if(m.double_chance_regulation)rows.push(["DUAL · gana o empata (60 min)",game.home+" 1X "+pct(m.double_chance_regulation.home),game.away+" X2 "+pct(m.double_chance_regulation.away)]);
  if(m.comeback_after_two_goal_deficit)rows.push(["Remontada: cae por 2 y gana",game.home+" "+pct(m.comeback_after_two_goal_deficit.home),game.away+" "+pct(m.comeback_after_two_goal_deficit.away)]);
  rows.forEach(row=>{const item=make("div",undefined,"nhl-joint-market");item.append(make("strong",row[0]),make("span",row[1]),make("span",row[2]));grid.append(item);});card.append(grid);
  if(m.comeback_after_two_goal_deficit)card.append(make("p","Cuenta si el equipo queda dos goles abajo en algún momento y aun así gana; el empate al final del tiempo regular se divide 50/50 para la prórroga del ML ilustrativo.","nhl-joint-footnote"));
  const context=scenario.division_rivalry;
  if(context){
   const details=make("details",undefined,"nhl-joint-context");
   const delta=context.applied_goal_differential_delta??context.expected_goal_differential_delta??0;
   const signed=typeof delta==="number"?(delta>0?"+":"")+delta.toFixed(2).replace(".",",")+" goles":"—";
   const status=context.applied_to_percentages?"Ajuste aplicado · "+signed+" al diferencial esperado":
    context.status==="insufficient_history"?"Sin ajuste · muestra histórica insuficiente":
    context.status==="context_only"?"Contexto divisional; sin señal histórica aplicable":"Sin cambio direccional histórico";
   details.append(make("summary","División y rivalidad · "+status));
   const evidence=context.evidence||{};
   for(const code of [game.home,game.away]){
    const row=evidence[code];
    if(row&&typeof row==="object")details.append(make("p",code+" · "+(row.division_games??0)+" partidos divisionales · "+(row.other_games??0)+" contra otras divisiones"));
   }
   if(Number.isFinite(evidence.head_to_head_games))details.append(make("p","Enfrentamientos directos previos: "+evidence.head_to_head_games));
   if(context.source&&context.source.latest_label_date)details.append(make("p","Historial oficial disponible hasta: "+context.source.latest_label_date));
   details.append(make("small","Solo resultados en tiempo regular anteriores a la fecha del partido · ajuste experimental, sin calibración."));
   card.append(details);
  }
  const props=scenario.player_probabilities||{};
  addPlayerProbabilities(card,game.home,props[game.home]);
  addPlayerProbabilities(card,game.away,props[game.away]);
  return card;
 }
 function render(){
  root.replaceChildren(make("h3","Modelo integrado NHL · escenarios"));const meta=make("div",undefined,"nhl-joint-meta");meta.append(make("span","Experimental · no calibrado","nhl-experimental-badge"));root.append(meta);
  root.append(make("p","Los goles proyectados por jugador alimentan los goles esperados y las probabilidades del partido. Las asistencias completan G+A=Puntos y generan probabilidades individuales de gol, asistencia y puntos por escenario de arquero. Es experimental, no calibrado ni reemplaza el baseline oficial de PULSO.","nhl-joint-note"));
  const status=make("p","Consultando última ejecución…","daily-source");root.append(status);
  if(!feed){status.textContent=error?"No se pudo cargar el modelo integrado: "+error:"El primer escenario aparecerá después de la próxima ejecución diaria.";return;}
  if(!validate(feed)){status.textContent="La publicación integrada no superó la validación. No se muestran sus probabilidades.";return;}
  if(!feed.date){status.textContent="Aún no hay una ejecución diaria publicada.";return;}
  const date=dateInput&&dateInput.value||feed.date;
  const lineupPending=feed.blocked_games.filter(g=>g.category==="lineup_not_confirmed").length;
  const otherPending=feed.blocked_games.length-lineupPending;
  status.textContent="Última captura: "+feed.date+" · "+feed.games.length+" partidos con escenarios integrados · "+lineupPending+" alineaciones por confirmar · "+otherPending+" pendientes por otros datos · publicada "+new Date(feed.published_at_utc).toLocaleString("es-CL",{timeZone:"America/Santiago",dateStyle:"short",timeStyle:"short"})+" (Chile)";
  if(date!==feed.date){root.append(make("p","No hay escenarios publicados para "+date+". La última captura es del "+feed.date+". No mostramos datos de otra fecha.","daily-empty"));return;}
  if(!feed.games.length&&!feed.blocked_games.length)root.append(make("p","La captura no encontró partidos elegibles para esta fecha.","daily-empty"));
  feed.games.forEach(game=>{const match=make("section",undefined,"nhl-joint-game");match.append(make("h4",game.away+" @ "+game.home));match.append(make("p",new Date(game.start_utc).toLocaleString("es-CL",{timeZone:"America/Santiago",dateStyle:"medium",timeStyle:"short"})+" · "+game.scenario_count+" combinaciones de arqueros","nhl-joint-kicker"));addRotowireEvidence(match,game);addRotowirePPAudit(match,game);for(const team of [game.home,game.away]){const info=game.minute_distribution&&game.minute_distribution[team]&&game.minute_distribution[team].return_to_play;const returns=info&&info.players;if(Array.isArray(returns)&&returns.length){const details=make("details",undefined,"nhl-joint-return");details.append(make("summary","Retorno tras lesión · "+team+" · "+returns.length+" jugador"+(returns.length===1?"":"es")));for(const player of returns){const applied=player.status==="adjustment_applied";const change=applied?"Ajuste experimental aplicado · "+player.minutes_before.toFixed(1)+" → "+player.minutes_after.toFixed(1)+" min":player.status==="insufficient_return_history"?"Sin ajuste · muestra histórica insuficiente ("+player.historical_players+" jugadores)":player.status==="minutes_reallocation_unavailable"?"Sin ajuste · no se pudieron redistribuir minutos":"Sin ajuste · "+player.status;details.append(make("p",player.name+" · "+change+" · "+player.days_out+" días desde el reporte"));}match.append(details);}}const mix=weighted(game);if(mix){const card=make("article",undefined,"nhl-joint-scenario");card.append(make("h5","Estimación combinada · titularidades históricas"));card.append(make("p","Goles esperados · "+game.home+" "+mix.expected_goals.home.toFixed(2)+" — "+mix.expected_goals.away.toFixed(2)+" "+game.away,"nhl-joint-goals"));const m=mix.markets;card.append(make("p","Ganador ilustrativo · "+game.home+" "+pct(m.illustrative_ml.home)+" · "+game.away+" "+pct(m.illustrative_ml.away)));card.append(make("p","Tiempo regular · "+game.home+" "+pct(m.regulation.home)+" · Empate "+pct(m.regulation.draw)+" · "+game.away+" "+pct(m.regulation.away)));card.append(make("p","Alcanza ventaja de +3 · "+game.home+" "+pct(m.three_goal_lead.home)+" · "+game.away+" "+pct(m.three_goal_lead.away)));card.append(make("p","Primero en +3 · "+game.home+" "+pct(m.first_to_three_goal_lead.home)+" · "+game.away+" "+pct(m.first_to_three_goal_lead.away)));if(m.strong_win_regulation)card.append(make("p","FUERTE · gana por 2+ en 60 min · "+game.home+" "+pct(m.strong_win_regulation.home)+" · "+game.away+" "+pct(m.strong_win_regulation.away)));if(m.double_chance_regulation)card.append(make("p","DUAL · gana o empata en 60 min · local 1X "+pct(m.double_chance_regulation.home)+" · visita X2 "+pct(m.double_chance_regulation.away)));if(m.comeback_after_two_goal_deficit)card.append(make("p","Remontada: cae por 2 y gana · "+game.home+" "+pct(m.comeback_after_two_goal_deficit.home)+" · "+game.away+" "+pct(m.comeback_after_two_goal_deficit.away)));const weightedPp=weightedPPImpactText(game);if(weightedPp)card.append(make("p",weightedPp,"nhl-joint-footnote"));match.append(card);}else{match.append(make("p","Sin estimación combinada: las titularidades históricas no cubren todos los partidos previos del equipo.","nhl-joint-footnote"));}game.scenarios.forEach((s,i)=>match.append(addScenario(game,s,i)));root.append(match);});
  if(feed.blocked_games.length){
   const pending=feed.blocked_games.filter(g=>g.category==="lineup_not_confirmed");
   if(pending.length){
    const details=make("details",undefined,"nhl-joint-blocked");details.append(make("summary",pending.length+" partidos: alineación aún no confirmada"));
    pending.forEach(g=>details.append(make("p",g.away+" @ "+g.home+" · Alineación aún no confirmada.")));
    root.append(details,make("p","El baseline de PULSO permanece vigente. El ajuste por líneas se incorpora cuando exista una proyección confirmada.","nhl-joint-footnote"));
   }
   const other=feed.blocked_games.filter(g=>g.category!=="lineup_not_confirmed");
   if(other.length){const details=make("details",undefined,"nhl-joint-blocked");details.append(make("summary",other.length+" escenarios integrados pendientes por otras fuentes"));other.forEach(g=>details.append(make("p",g.away+" @ "+g.home+" · "+g.reason)));root.append(details);}
  }
  root.append(make("p","La estimación combinada usa la proporción de partidos iniciados por cada candidato en la temporada actual. Solo aparece si el historial de candidatos cubre todos los partidos previos del equipo. Es una frecuencia descriptiva sin calibración; el modelo sigue siendo experimental y no oficial.","nhl-joint-footnote"));
 }
 doc.addEventListener("pulso:date-change",render);if(dateInput)dateInput.addEventListener("change",render);render();
 fetch("./data/nhl-rotowire-pregame-latest.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();}).then(data=>{if(data&&data.kind==="nhl_rotowire_reconciled_pregame_v475"&&data.official===false&&data.probabilities_modified===false)rotowireFeed=data;render();}).catch(()=>{rotowireFeed=null;});
 fetch("./data/nhl-joint-model-latest.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();}).then(data=>{if(!validate(data))throw new Error("formato no válido");feed=data;error=null;render();}).catch(e=>{error=e.message;render();});
})(typeof window!=="undefined"?window:globalThis);
