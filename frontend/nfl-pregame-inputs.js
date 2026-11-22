"use strict";
(function(scope){
 const api={snapshot:null,ready:Promise.resolve()};
 if(typeof document==="undefined"){scope.PulsoNflInputs=api;return;}
 api.ready=fetch("./data/nfl-pregame-inputs-latest.json",{cache:"no-store"}).then(r=>{if(!r.ok)throw Error("HTTP "+r.status);return r.json();})
  .then(d=>{if(d.kind!=="nfl_pregame_input_inventory_v1"||!Array.isArray(d.games))throw Error("Invalid inventory");api.snapshot=d;}).catch(()=>{});
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const fmt=v=>v==null||v===""?"Sin dato":Array.isArray(v)?(v.length?v.map(fmt).join(" · "):"Ninguno reportado"):typeof v==="object"?Object.entries(v).filter(([,x])=>x!=null).map(([k,x])=>k.replaceAll("_"," ")+": "+fmt(x)).join(" · "):String(v);
 api.append=(container,event)=>{
  const g=api.snapshot?.games.find(x=>String(x.event_id)===String(event.event_id)&&x.home===event.participants[0]&&x.away===event.participants[1]&&Date.parse(x.start_utc)===Date.parse(event.start_utc));
  const root=el("details",undefined,"nfl-input-inventory");
  root.append(el("summary",g?"Entradas del partido · capturadas y pendientes":"Entradas del partido · ficha pendiente"));
  if(!g){root.append(el("p","La próxima corrida NFL publicará la ficha de datos para este encuentro.","nfl-input-note"));container.append(root);return;}
  root.append(el("p","Captura "+new Date(api.snapshot.generated_at_utc).toLocaleString("es-CL",{timeZone:"America/Santiago",dateStyle:"medium",timeStyle:"short"})+" · Elo exploratorio, sin certificación.","nfl-input-note"));
  for(const group of g.groups||[]){
   const part=el("details",undefined,"nfl-input-group");part.append(el("summary",group.title));
   const grid=el("div",undefined,"nfl-input-grid");
   for(const r of group.rows||[]){
    const card=el("article",undefined,"nfl-input-row nfl-input-"+(r.status||"missing")),head=el("div",undefined,"nfl-input-row-top");
    head.append(el("strong",r.label),el("span",({captured:"Capturado",partial:"Incompleto",missing:"Pendiente"})[r.status]||"Revisar","nfl-input-state"));
    card.append(head,el("p",fmt(r.value),"nfl-input-value"),el("p",r.used_in_base_probability?"Sí entra al porcentaje candidato":"No cambia el porcentaje de esta corrida","nfl-input-effect"));
    if(r.use_note)card.append(el("p",r.use_note,"nfl-input-note"));if(r.gap)card.append(el("p","Pendiente: "+r.gap,"nfl-input-gap"));
    const url=r.source?.url;if(typeof url==="string"&&/^https:\/\//.test(url)){const a=el("a","Ver fuente");a.href=url;a.target="_blank";a.rel="noopener noreferrer";card.append(a);}
    grid.append(card);
   }
   part.append(grid);root.append(part);
  }
  container.append(root);
 };
 scope.PulsoNflInputs=api;
})(typeof window==="undefined"?globalThis:window);
