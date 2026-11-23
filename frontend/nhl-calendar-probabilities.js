"use strict";
(function(){
 if(new URLSearchParams(location.search).get("sport")!=="nhl")return;
 const ROOT="./data/forecast-index.json";
 const root=document.getElementById("daily-results");
 const day=value=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(value));
 const key=value=>String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]+/g," ").trim();
 const pct=value=>(100*value).toLocaleString("es-CL",{minimumFractionDigits:1,maximumFractionDigits:1})+" %";
 const dateLabel=value=>new Date(value).toLocaleString("es-CL",{timeZone:"America/Santiago",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"});
 let records=null;
 function valid(data){
  return data&&data.kind==="progressive_forecast_index"&&Array.isArray(data.events)&&Array.isArray(data.errors)&&
   data.events.every(e=>typeof e.sport==="string"&&typeof e.event_id==="string"&&Array.isArray(e.participants)&&e.participants.length===2&&
    e.latest&&e.initial&&e.latest.probabilities&&e.initial.probabilities&&Number.isFinite(Date.parse(e.start_utc)));
 }
 function teamsIn(card){
  const summary=card.querySelector(":scope > summary");
  if(!summary)return [];
  return ["away","home"].map(side=>{
   const node=summary.querySelector(".daily-team-"+side),label=node?.querySelector(".daily-team-name")?.textContent||node?.getAttribute("aria-label")||"";
   const img=node?.querySelector("img")?.getAttribute("src")||"";
   const code=img.match(/\/([A-Z]{3})_light\.svg(?:\?|$)/)?.[1]||"";
   return {side,label,code};
  });
 }
 function matchingRecord(card,date){
  const pair=teamsIn(card);
  if(!pair.every(x=>x.label))return null;
  const events=records.events.filter(e=>e.sport==="nhl"&&day(e.start_utc)===date);
  const id=String(card.dataset.gameId||"");
  return events.find(e=>id&&e.event_id===id)||events.find(e=>{
   const participants=e.participants.map(value=>key(value));
   return pair.every(team=>participants.includes(key(team.label))||Boolean(team.code&&e.participants.some(value=>String(value).toUpperCase()===team.code)));
  })||null;
 }
 function make(tag,text,className){
  const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;
 }
 function render(){
  if(!records||!root)return;
  const selected=document.getElementById("daily-date")?.value;
  if(!selected)return;
  for(const card of root.querySelectorAll(".nba-game-disclosure[data-game-id]")){
   const panel=card.querySelector(".nba-game-disclosure__run-panel");
   if(!panel)continue;
   const existing=panel.querySelector(".nhl-calendar-probability");
   const record=matchingRecord(card,selected);
   if(!record){existing?.remove();continue;}
   if(existing)continue;
   panel.querySelectorAll(".nba-game-disclosure__empty").forEach(node=>node.remove());
   const pair=teamsIn(card),eventParticipants=record.participants;
   const section=make("div",undefined,"nhl-calendar-probability");
   section.append(make("p","Probabilidad de ganador · "+dateLabel(record.latest.emitted_at_utc),"nhl-calendar-probability__meta"));
   const rows=make("div",undefined,"nhl-calendar-probability__rows");
   for(const team of pair){
    const participantIndex=eventParticipants.findIndex(value=>key(value)===key(team.label)||Boolean(team.code&&String(value).toUpperCase()===team.code));
    if(participantIndex<0)continue;
    const probabilityKey=participantIndex===0?"home":"away";
    const current=record.latest.probabilities[probabilityKey],initial=record.initial.probabilities[probabilityKey];
    if(!Number.isFinite(current)||current<=0||current>=1)continue;
    const row=make("div",undefined,"nhl-calendar-probability__row");
    row.append(make("span",team.label),make("strong",pct(current)));
    rows.append(row);
    const delta=current-initial;
    if(Number.isFinite(delta)&&Math.abs(delta)>=0.0005){
     row.append(make("small","Desde la inicial: "+(delta>0?"+":"−")+pct(Math.abs(delta))));
    }
   }
   if(!rows.children.length)continue;
   section.append(rows);
   const model=record.latest.model_version||"Modelo experimental";
   section.append(make("p",model+" · "+record.history.length+" corrida"+(record.history.length===1?"":"s")+" · Sin calibración certificada.","nhl-calendar-probability__note"));
   panel.append(section);
  }
  const market=document.querySelector("#nhl-five-market .daily-empty");
  if(market&&records.events.some(e=>e.sport==="nhl"&&day(e.start_utc)===selected)){
   market.textContent="El pronóstico de ganador está dentro de cada partido del calendario. No se publicaron mercados de goles para esta fecha.";
  }
 }
 document.addEventListener("pulso:date-change",render);
 document.getElementById("daily-date")?.addEventListener("change",render);
 if(root){
  const observer=new MutationObserver(()=>render());
  observer.observe(root,{childList:true,subtree:true});
 }
 fetch(ROOT,{cache:"no-store"}).then(response=>{
  if(!response.ok)throw Error("No se pudo cargar el registro de probabilidades.");
  return response.json();
 }).then(data=>{
  if(!valid(data))throw Error("Registro de probabilidades no válido.");
  records=data;render();
 }).catch(()=>{});
})();