"use strict";
(async function(){
 const root=document.getElementById("pulso-nhl-research");
 if(!root || new URLSearchParams(location.search).get("sport")!=="nhl")return;
 const status=document.createElement("p");status.textContent="Consultando predicciones NHL verificables…";root.append(status);
 const section=(title)=>{const block=document.createElement("section");const h=document.createElement("h4");h.textContent=title;block.append(h);root.append(block);return block;};
 const p=(parent,value)=>{const el=document.createElement("p");el.textContent=value;parent.append(el);return el;};
 const percent=value=>(value*100).toFixed(1)+" %";
 async function get(path){const response=await fetch(path,{cache:"no-store"});if(!response.ok)throw new Error(String(response.status));return response.json();}
 try{
  const latest=await get("./data/nhl-shadow/latest.json");
  if(latest.kind!=="prospective_challenger_shadow" || !Array.isArray(latest.games))throw new Error("Formato shadow inválido");
  status.textContent="NHL · Challenger ML experimental (modo sombra). No es modelo oficial ni recomendación de apuesta.";
  const predictions=section("Pronósticos congelados del challenger");
  p(predictions,"Modelo: "+latest.model_version+" · Fecha de captura: "+new Date(latest.generated_at_utc).toLocaleString("es-CL",{dateStyle:"medium",timeStyle:"short"}));
  const valid=latest.games.filter(x=>x.status==="shadow_prediction");
  if(!valid.length)p(predictions,"No hay pronósticos elegibles publicados en esta ejecución.");
  valid.forEach(g=>{
   const row=document.createElement("div");row.className="nhl-model-row";
   const h=document.createElement("strong");h.textContent=g.away+" @ "+g.home;row.append(h);
   p(row,"ML "+g.home+": "+percent(g.p_home_ml)+" · "+g.away+": "+percent(g.p_away_ml));
   p(row,"Inicio: "+new Date(g.start_utc).toLocaleString("es-CL",{dateStyle:"medium",timeStyle:"short"})+" · Investigación; sin cuotas.");
   predictions.append(row);
  });
  const blocked=latest.games.filter(x=>x.status==="blocked");
  if(blocked.length)p(predictions,blocked.length+" partidos bloqueados por evidencia insuficiente.");
 }catch(_){status.textContent="NHL: aún no hay una publicación del último pronóstico experimental. No se muestran probabilidades no verificadas.";}
 const evaluation=section("Baseline vs. challenger · seguimiento prospectivo");
 try{
  const report=await get("./data/pulso-nhl-ml-comparison.json");
  if(report.status!=="prospective_paired_ml_evaluation")throw new Error("Reporte no válido");
  p(evaluation,"Partidos completados comparables: "+report.paired_completed+". Pendientes con ambos pronósticos: "+report.paired_awaiting_official_final.length+".");
  if(report.metrics){
   p(evaluation,"Brier: baseline "+report.metrics.brier.baseline.toFixed(4)+" / challenger "+report.metrics.brier.challenger.toFixed(4)+".");
   p(evaluation,"Log Loss: baseline "+report.metrics.log_loss.baseline.toFixed(4)+" / challenger "+report.metrics.log_loss.challenger.toFixed(4)+".");
  }else p(evaluation,"Esperando resultados finales y pronósticos comparables. No hay métricas prospectivas disponibles.");
  p(evaluation,"Solo se puntúan predicciones anteriores al inicio y encuentros con marcador final oficial.");
 }catch(_){p(evaluation,"Comparación prospectiva aún no publicada. Sin resultados inventados.");}
})();
