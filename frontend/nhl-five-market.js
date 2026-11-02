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
 let published=null,loadError=null;
 function render(){
 root.replaceChildren(make("h3","Pronósticos de la jornada"));
 const source=make("p","Cargando captura…","daily-source");
 const meta=make("div",undefined,"nhl-market-meta");
 meta.append(make("span","Experimental","nhl-experimental-badge"),source);root.append(meta);
 const note=make("p","Probabilidades del modelo histórico. Sin cuotas; no equivalen a certeza ni recomendación de apuesta.","nhl-probability-note");
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
   const card=make("section",undefined,"nhl-forecast-card");
   const heading=make("div",undefined,"nhl-forecast-heading"),identity=make("div");
   identity.append(make("h4",g.away+" — "+g.home),make("p",new Date(g.start_utc).toLocaleString("es-CL",{timeZone:"America/Santiago",dateStyle:"medium",timeStyle:"short"})+" · Chile"));
   const pending=Date.parse(g.start_utc)>Date.now();
   heading.append(identity,make("span",pending?"Por comenzar":"Captura pregame","nhl-upcoming"));card.append(heading);
   const valid=g.ml&&g.rt&&g.first_to_plus3&&typeof g.home_plus3==="number"&&typeof g.away_plus3==="number";
   if(!valid){card.append(make("p","Mercados incompletos: no se muestran probabilidades parciales."));root.append(card);continue;}
   card.append(make("div","Probabilidad base · incluye desempate","nhl-market-label"));
   const probabilities=make("div",undefined,"nhl-ml-grid");
   for(const [team,value] of [[g.away,g.ml.away],[g.home,g.ml.home]]){
    const side=make("div",undefined,"nhl-probability");side.append(make("span",team),make("strong",pct(value)));probabilities.append(side);
   }
   card.append(probabilities);
   card.append(window.PulsoNhlGoalieComparison.create(data,g));
   card.append(window.PulsoNhlContext.create(g));
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
 document.addEventListener("pulso:date-change",render);
 window.PulsoNhlContext.ready.then(render);
 window.PulsoNhlGoalieComparison.ready.then(render);
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
