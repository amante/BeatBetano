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
 const source=make("p","Cargando resultados de la última captura NHL…","daily-source");
 root.append(source);
 const control=make("p");
 const link=make("a","Ejecutar nueva captura pregame en GitHub Actions");
 link.href="https://github.com/amante/BeatBetano/actions/workflows/pulso-nhl-prospective.yml";
 link.target="_blank";link.rel="noopener noreferrer";
 control.append(link,document.createTextNode(" · Requiere permisos en GitHub; la página pública no ejecuta workflows por sí sola."));
 root.append(control);
 const warn=make("p","Modelo histórico experimental #218; no incorpora probabilidades condicionadas por arquero, cuotas ni validación del modelo deportivo completo.","daily-source");
 root.append(warn);
 try{
  const response=await fetch("./data/nhl-daily-predictions-latest.json",{cache:"no-store"});
  if(!response.ok)throw new Error("HTTP "+response.status);
  const data=await response.json();
  if(data.kind!=="nhl_research_daily_presentation_275" || data.official!==false ||
     data.odds_used!==false || !Array.isArray(data.games) ||
     data.official_schedule_games!==data.games.length ||
     data.games.some(g=>!g.game_id||!g.home||!g.away||!g.start_utc))throw new Error("Reporte no verificado");
  source.textContent="Calendario NHL "+data.date+" · "+data.games.length+" partidos oficiales · "+data.experimental_predicted_games+" con los cinco mercados. Datos de la última ejecución publicada.";
  if(!data.games.length){root.append(make("p","Sin partidos programados en la fecha de la captura.","daily-empty"));return;}
  const plus3=window.PulsoNhlPlus3.summarize(data.games);
  root.append(make("p",plus3.count?"Promedio +3 de la jornada: "+pct(plus3.mean)+" · "+plus3.count+" pronósticos de equipos. ↑ Sobre promedio destaca valores estrictamente superiores; no indica valor de apuesta.":"Sin probabilidades +3 para calcular un promedio.","daily-source"));
  for(const g of data.games){
   const card=make("section",undefined,"nhl-model-row");
   card.append(make("strong",g.away+" @ "+g.home));
   card.append(make("p","Inicio Chile: "+new Date(g.start_utc).toLocaleString("es-CL",{timeZone:"America/Santiago",dateStyle:"medium",timeStyle:"short"})));
   if(g.status!=="experimental_forecast"){
    card.append(make("p",g.status==="not_pregame_at_capture"?"Sin pronóstico: el encuentro ya no estaba en estado pregame.":"Sin pronóstico verificable disponible."));
    root.append(card);continue;
   }
   const valid=g.ml&&g.rt&&g.first_to_plus3&&typeof g.home_plus3==="number"&&typeof g.away_plus3==="number";
   if(!valid){card.append(make("p","Mercados incompletos: no se muestran probabilidades parciales."));root.append(card);continue;}
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
   card.append(table);root.append(card);
  }
 }catch(e){
  source.textContent="Todavía no se ha publicado una cartelera NHL completa verificable ("+e.message+").";
 }
})();
