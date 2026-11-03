"use strict";
(async function(){
 const root=document.getElementById("nhl-postmortem");if(!root)return;
 const make=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
 const names={ml:"Ganador",rt:"Tiempo regular",home3:"Local alcanza +3",away3:"Visitante alcanza +3",first3:"Primero en +3"};
 let index=null,selected=null;
 const reports=new Map();
 const teamNames={ANA:"Anaheim Ducks",BOS:"Boston Bruins",BUF:"Buffalo Sabres",CAR:"Carolina Hurricanes",CBJ:"Columbus Blue Jackets",CGY:"Calgary Flames",CHI:"Chicago Blackhawks",COL:"Colorado Avalanche",DAL:"Dallas Stars",DET:"Detroit Red Wings",EDM:"Edmonton Oilers",FLA:"Florida Panthers",LAK:"Los Angeles Kings",MIN:"Minnesota Wild",MTL:"Montréal Canadiens",NJD:"New Jersey Devils",NSH:"Nashville Predators",NYI:"New York Islanders",NYR:"New York Rangers",OTT:"Ottawa Senators",PHI:"Philadelphia Flyers",PIT:"Pittsburgh Penguins",SEA:"Seattle Kraken",SJS:"San Jose Sharks",STL:"St. Louis Blues",TBL:"Tampa Bay Lightning",TOR:"Toronto Maple Leafs",UTA:"Utah Mammoth",VAN:"Vancouver Canucks",VGK:"Vegas Golden Knights",WPG:"Winnipeg Jets",WSH:"Washington Capitals"};
 function team(code,score,winner){const el=make("span");el.className="postmortem-team";
  if(Object.hasOwn(teamNames,code)){const img=make("img");img.src="https://assets.nhle.com/logos/nhl/svg/"+code+"_light.svg";img.alt="";img.width=40;img.height=40;img.loading="lazy";img.addEventListener("error",()=>img.remove());el.append(img);}
  el.append(make("span",teamNames[code]||code));if(Number.isInteger(score)){const points=make("strong",String(score));points.className="postmortem-score";el.append(points);}if(winner){const trophy=make("span","🏆");trophy.setAttribute("aria-label","Ganador");el.append(trophy);}return el;
 }
 function gamesView(data){const list=make("div");list.className="postmortem-games";
  for(const game of data.games||[]){const card=make("article");card.className="postmortem-game";
   const final=game.state==="OFF"||game.state==="FINAL";
   const winner=game.outcomes?.ml_winner;
   const title=make("h5");title.append(team(game.away,final?game.away_score:null,final&&winner==="away"),make("span","—"),team(game.home,final?game.home_score:null,final&&winner==="home"));card.append(title);
   if(!final)card.append(make("p","Resultado pendiente"));
   const label=k=>k==="home"?(teamNames[game.home]||game.home):k==="away"?(teamNames[game.away]||game.away):k==="draw"?"Empate":k==="none"?"Ninguno":k==="yes"?"Sí":k==="no"?"No":k;
   const rows=(data.market_scores||[]).filter(r=>String(r.game_id)===String(game.game_id));
   if(!rows.length)card.append(make("p","Sin pronóstico guardado para este partido."));
   for(const row of rows){const probability=row.probabilities?.[row.modal_class];const binary=row.market==="home3"||row.market==="away3";const side=row.market==="home3"?game.home:game.away;
    const selection=binary?(teamNames[side]||side)+(row.modal_class==="yes"?" SÍ alcanza una ventaja de 3 goles":" NO alcanza una ventaja de 3 goles"):label(row.modal_class);
    const text=(binary?"Ventaja +3":names[row.market]||row.market)+": "+selection+(Number.isFinite(probability)?" ("+(probability*100).toFixed(1)+"%)":"")+" · "+(row.modal_correct===true?"Acertado":row.modal_correct===false?"Fallado":"Pendiente");const p=make("p",text);if(row.market==="ml")p.className="postmortem-pick";card.append(p);}
   list.append(card);
  }return list;
 }
 async function loadDay(day){reports.set(day,{loading:true});try{const response=await fetch("./data/nhl-postmortems/"+day+".json",{cache:"no-store"});if(!response.ok)throw Error();const data=await response.json();if(data.kind!=="nhl_daily_postmortem"||data.date!==day)throw Error();reports.set(day,data);}catch{reports.set(day,{error:true});}render();}
 function render(){
  root.replaceChildren(make("h4","Post mortem automático"));
  if(!index){root.append(make("p","El cierre diario aparecerá aquí cuando se publique la primera auditoría."));return;}
  const dates=index.days||[];const previous=new Date(document.getElementById("daily-date").value+"T12:00:00Z");previous.setUTCDate(previous.getUTCDate()-1);
  const target=selected||previous.toISOString().slice(0,10),report=dates.find(x=>x.date===target);
  const select=make("select");select.setAttribute("aria-label","Fecha del post mortem");
  if(!report){const option=make("option",target+" · Pendiente");option.value=target;select.append(option);}
  for(const day of [...dates].reverse()){const option=make("option",day.date);option.value=day.date;select.append(option);}select.value=target;
  select.addEventListener("change",()=>{selected=select.value;render();});root.append(select);
  if(!report){root.append(make("p","Todavía no está publicado el cierre de esta fecha. Se revisan las últimas siete jornadas dos veces al día."));return;}
  const state={complete:"Cierre completo",pending_results:"Esperando resultados finales",needs_review:"Hay fuentes que requieren revisión",no_forecasts:"No hubo pronósticos guardados"}[report.status]||report.status;
  root.append(make("p",state+" · "+report.graded_games+" partidos evaluados · "+report.market_forecasts_scored+" predicciones de mercado."));
  const detail=reports.get(report.date);
  if(!detail){void loadDay(report.date);root.append(make("p","Cargando partidos y pronósticos…"));}
  else if(detail.error)root.append(make("p","No se pudieron cargar los partidos. Recarga la página para volver a intentarlo."));
  else if(detail.loading)root.append(make("p","Cargando partidos y pronósticos…"));
  else {root.append(make("p","+3 significa conseguir una ventaja de tres goles, no marcar tres goles en total. En cada línea, el porcentaje corresponde al pronóstico escrito, incluido NO. Ser primero en +3 es un mercado distinto."));root.append(gamesView(detail));}
  const technical=make("details");technical.append(make("summary","Métricas y aprendizaje"));
  const metrics=make("ul");
  for(const row of report.metrics||[])metrics.append(make("li",(names[row.market]||row.market)+": "+row.modal_correct+"/"+row.n+" en la opción más probable · Brier "+row.brier.toFixed(4)));
  if(metrics.children.length)technical.append(metrics);root.append(technical);
  root.append(make("p","Las predicciones repetidas no se cuentan varias veces. El aprendizaje se guarda como observaciones; los parámetros no cambian automáticamente."));
  const link=make("a","Ver informe y métricas completas");link.href="./data/nhl-postmortems/"+report.date+".json";link.target="_blank";link.rel="noopener noreferrer";root.append(link);
 }
 document.addEventListener("pulso:date-change",()=>{selected=null;render();});render();
 try{const response=await fetch("./data/nhl-postmortem-latest.json",{cache:"no-store"});if(!response.ok)throw Error("No publication");const data=await response.json();if(data.kind!=="nhl_postmortem_index"||!Array.isArray(data.days))throw Error("Invalid index");index=data;render();}catch{render();}
})();
