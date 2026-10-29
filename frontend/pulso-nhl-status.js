"use strict";
(async function(){
 const root=document.getElementById("pulso-nhl-research");
 if(!root || new URLSearchParams(location.search).get("sport")!=="nhl")return;
 const line=document.createElement("p");
 line.textContent="Estado del motor: sin predicciones colectivas verificadas publicadas.";
 root.append(line);
 try{
  const response=await fetch("./data/pulso-nhl-research.json",{cache:"no-store"});
  if(!response.ok)return;
  const doc=await response.json();
  if(!Array.isArray(doc.games))return;
  line.textContent="Motor NHL experimental: "+doc.games.length+" registros de investigación. No son pronósticos oficiales ni recomendaciones de apuesta.";
  for(const g of doc.games){
   const row=document.createElement("p");
   const state=g.status==="research_only_not_calibrated"?"Simulación experimental sin calibrar":"Predicción no disponible";
   row.textContent=[g.away,g.home].join(" @ ")+" — "+state+(Array.isArray(g.readiness_issues)&&g.readiness_issues.length?" ("+g.readiness_issues.join(", ")+")":"");
   root.append(row);
  }
 }catch(_){line.textContent="Motor NHL: no hay resultados de investigación verificados disponibles.";}
})();
