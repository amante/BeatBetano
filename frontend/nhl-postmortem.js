"use strict";
(async function(){
 const root=document.getElementById("nhl-postmortem");if(!root)return;
 const make=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
 const names={ml:"Ganador",rt:"Tiempo regular",home3:"Local alcanza +3",away3:"Visitante alcanza +3",first3:"Primero en +3"};
 let index=null,selected=null;
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
  const metrics=make("ul");
  for(const row of report.metrics||[])metrics.append(make("li",(names[row.market]||row.market)+": "+row.modal_correct+"/"+row.n+" en la opción más probable · Brier "+row.brier.toFixed(4)));
  if(metrics.children.length)root.append(metrics);
  root.append(make("p","Las predicciones repetidas no se cuentan varias veces. El aprendizaje se guarda como observaciones; los parámetros no cambian automáticamente."));
  const link=make("a","Ver informe y métricas completas");link.href="./data/nhl-postmortems/"+report.date+".json";link.target="_blank";link.rel="noopener noreferrer";root.append(link);
 }
 document.addEventListener("pulso:date-change",()=>{selected=null;render();});render();
 try{const response=await fetch("./data/nhl-postmortem-latest.json",{cache:"no-store"});if(!response.ok)throw Error("No publication");const data=await response.json();if(data.kind!=="nhl_postmortem_index"||!Array.isArray(data.days))throw Error("Invalid index");index=data;render();}catch{render();}
})();
