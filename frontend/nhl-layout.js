"use strict";
// Presentation only: retain the existing dispatcher, source checks and element IDs.
if(new URLSearchParams(location.search).get("sport")==="nhl"){
 document.body.classList.add("nhl-dashboard");
 const byId=id=>document.getElementById(id);
 const make=(tag,cls,text)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text)el.textContent=text;return el;};
 const disclosure=(title,cls,...children)=>{const el=make("details",cls);el.append(make("summary",null,title),...children);return el;};
 const main=document.querySelector("main");
 const intro=make("section","nhl-intro");intro.id="nhl-overview";
 intro.append(make("div","eyebrow","PULSO / NHL"),make("h1",null,"Tu jornada, de un vistazo."),make("p","nhl-lead","Encuentros pendientes y probabilidades, antes del inicio."));
 const summary=make("div","nhl-summary");summary.id="nhl-day-summary";summary.setAttribute("role","status");intro.append(summary);
 const grid=make("div","nhl-workspace-grid");
 const predictions=byId("nhl-five-market");predictions.querySelector("h3").textContent="Pronósticos de la jornada";
 const run=document.querySelector(".simulation-panel");run.id="nhl-run-panel";
 run.querySelector(".eyebrow").textContent="ACTUALIZAR ANÁLISIS";
 byId("simulation-title").textContent="Ejecutar modelo";
 const description=run.querySelector(".section-header p");description.id="nhl-pending-summary";description.textContent="Consultando encuentros pendientes…";
 run.querySelector('input[value="all"]').checked=true;
 run.querySelector("fieldset").hidden=true;
 byId("run-simulation").textContent="Ejecutar jornada NHL";
 run.append(make("p","nhl-run-note","Se procesa la jornada completa. Solo se generan nuevos pronósticos para encuentros que aún no comienzan."));
 grid.append(predictions,run);
 const agenda=byId("daily-panel");agenda.querySelector(".eyebrow").textContent="CALENDARIO · HORA DE CHILE";
 const history=disclosure("Historial y resultados","panel nhl-disclosure",byId("daily-stats"),document.querySelector(".daily-yesterday"));history.id="nhl-history";
 const sources=disclosure("Fuente y actualización del calendario","nhl-source-details",byId("feed-message"));
 agenda.append(sources);
 const research=byId("pulso-nhl-research");research.querySelector("h3").textContent="Comparación de modelos";
 const method=disclosure("Metodología y seguimiento experimental","panel nhl-disclosure",make("p",null,"Probabilidades experimentales; no son recomendaciones de apuesta. El modelo principal usa resultados históricos y no incorpora cuotas ni probabilidades condicionadas por arquero."),research);method.id="nhl-method";
 main.prepend(intro,grid);main.append(agenda,history,method);
 for(const button of document.querySelectorAll("[data-nav]")){
  const target={overview:"nhl-overview",games:"nhl-five-market",calibration:"nhl-history"}[button.dataset.nav];
  if(button.dataset.nav==="games")button.lastChild.textContent=" Jornada y pronósticos";
  if(button.dataset.nav==="calibration")button.lastChild.textContent=" Historial";
  button.addEventListener("click",()=>{
   const element=byId(target);if(element.tagName==="DETAILS")element.open=true;
   element.scrollIntoView({behavior:matchMedia("(prefers-reduced-motion: reduce)").matches?"instant":"smooth",block:"start"});
   document.querySelectorAll("[data-nav]").forEach(b=>b.classList.toggle("active",b===button));
   document.querySelector(".sidebar").classList.remove("open");
  });
 }
}
