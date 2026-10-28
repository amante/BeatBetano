"use strict";
const SPORTS=[["nba","NBA","🏀","Motor en desarrollo"],["nfl","NFL","🏈","Motor en desarrollo"],["nhl","NHL","🏒","Histórico y calibración"],["soccer","Fútbol","⚽","Motor pendiente"],["tennis","Tenis","🎾","Motor pendiente"]];
let reports=[],section="overview",selectedSport="all";
const $=id=>document.getElementById(id);
function node(tag,text,className){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}
function renderSports(){
 const list=$("sports-list"),nav=$("sport-nav");list.replaceChildren();nav.replaceChildren();
 for(const [id,name,emoji,description] of SPORTS){
  const item=node("div",undefined,"sport-row"),symbol=node("span",emoji,"sport-icon"),copy=node("div"),label=node("strong",name),sub=node("small",description),tag=node("span",reports.some(x=>x.sport===id)?"CARGADO":"SIN DATOS","tag");
  copy.append(label,sub);item.append(symbol,copy,tag);list.append(item);
  const button=node("button",emoji+"  "+name,"nav");button.type="button";button.dataset.sport=id;button.addEventListener("click",()=>{selectedSport=id;$("sport-filter").value=id;setSection("games");});nav.append(button);
 }
}
function setSection(which){
 section=which;document.querySelectorAll("[data-nav]").forEach(x=>x.classList.toggle("active",x.dataset.nav===which));
 const labels={overview:["VISIÓN GENERAL","Centro de inteligencia deportiva","Cinco disciplinas, una arquitectura de evidencia. Sin pronósticos inventados."],games:["PARTIDOS Y MODELOS","Explorador de partidos","Pronósticos finales solo cuando el reporte declare validación."],calibration:["CALIBRACIÓN","Estado de calibración","Los reportes importados mantienen su estado de certificación original."]};
 const [crumb,title,desc]=labels[which];$("crumb").textContent=crumb;$("page-title").replaceChildren(node("span",title),node("span",".","dot"));$("page-desc").textContent=desc;$("list-title").textContent=which==="calibration"?"Evidencia de modelos":"Partidos y cobertura";
}
function parseReport(value){
 if(!value||typeof value!=="object"||Array.isArray(value))throw Error("El reporte debe ser un objeto JSON.");
 const sport=value.sport;if(!SPORTS.some(x=>x[0]===sport))throw Error("Se requiere un deporte válido: nba, nfl, nhl, soccer o tennis.");
 const items=Array.isArray(value.events)?value.events:Array.isArray(value.games)?value.games:Array.isArray(value.predictions)?value.predictions:null;
 if(!items)throw Error("No hay lista de eventos (events, games o predictions).");
 if(items.length>5000)throw Error("El archivo supera el límite de 5.000 eventos.");
 const asOf=value.as_of_utc||value.created_at_utc||null;
 if(asOf&&!Number.isFinite(Date.parse(asOf)))throw Error("Fecha de reporte no válida.");
 const records=items.map((item,i)=>{
  if(!item||typeof item!=="object")throw Error("Evento inválido en posición "+i);
  const home=item.home_team||item.home||item.participants?.[0];
  const away=item.away_team||item.away||item.participants?.[1];
  const id=item.event_id??item.game_id;
  if(!home||!away||id===undefined||id===null)throw Error("Partido sin identificador o equipos en posición "+i);
  const p=item.final_probability;
  const validated=p!==null&&p!==undefined&&item.all_inputs_verified===true&&item.independent_validation_passed===true&&Boolean(item.validation_report_ref)&&Number.isFinite(p)&&p>0&&p<1;
  return {id:String(id),home:String(home),away:String(away),sport,validated,p:validated?p:null,
   candidate:Boolean(item.source_candidate_available||item.illustrative_ml||item.statistical_p_home!==undefined||item.baseline_p_home!==undefined)};
 });
 if(new Set(records.map(x=>x.id)).size!==records.length)throw Error("Identificadores duplicados en el reporte.");
 return {sport,asOf,records};
}
function refresh(){
 const all=reports.flatMap(r=>r.records),keyword=$("search").value.trim().toLocaleLowerCase("es");
 const filtered=all.filter(r=>(selectedSport==="all"||r.sport===selectedSport)&&(!keyword||(r.home+" "+r.away).toLocaleLowerCase("es").includes(keyword)));
 const rows=$("rows");rows.replaceChildren();
 if(!filtered.length){const tr=node("tr"),td=node("td",all.length?"No hay partidos para este filtro.":"No hay reportes cargados. Importa un JSON para ver partidos.","empty");td.colSpan=5;tr.append(td);rows.append(tr);}
 for(const r of filtered){
  const tr=node("tr");const name=SPORTS.find(s=>s[0]===r.sport)?.[1]||r.sport;
  for(const content of [r.away+" @ "+r.home,name,r.validated?"Validado":r.candidate?"Experimental":"Sin datos",r.validated?(r.p*100).toFixed(1)+" %":"—"]){tr.append(node("td",content));}
  const td=node("td"),badge=node("span",r.validated?"Validado":"Sin validar","status"+(r.validated?" good":""));td.append(badge);tr.append(td);rows.append(tr);
 }
 $("metric-events").textContent=String(all.length).padStart(2,"0");
 const validated=all.filter(r=>r.validated).length;$("metric-validated").textContent=String(validated).padStart(2,"0");
 $("metric-state").textContent=all.length?"CARGADO":"PENDIENTE";$("metric-state-help").textContent=all.length?reports.length+" reporte(s) importado(s)":"Importa un reporte para comenzar";
 $("row-count").textContent=filtered.length+" eventos";
 const last=reports.filter(x=>x.asOf).map(x=>Date.parse(x.asOf)).filter(Number.isFinite).sort((a,b)=>b-a)[0];
 $("last-update").textContent=last?new Date(last).toLocaleString("es-CL",{dateStyle:"medium",timeStyle:"short"}):"Sin fecha de actualización";
 renderSports();
}
function message(text,error=false){$("messages").textContent=text;$("messages").classList.toggle("error",error);}
async function importFile(file){
 if(!file)return;
 if(file.size>5*1024*1024)throw Error("El JSON excede 5 MB.");
 const report=parseReport(JSON.parse(await file.text()));
 const ix=reports.findIndex(x=>x.sport===report.sport);
 if(ix>=0)reports[ix]=report;else reports.push(report);
 message("Reporte "+report.sport.toUpperCase()+" cargado localmente: "+report.records.length+" eventos.");
 refresh();
}
document.querySelectorAll("[data-nav]").forEach(btn=>btn.addEventListener("click",()=>setSection(btn.dataset.nav)));
$("sport-filter").addEventListener("change",e=>{selectedSport=e.target.value;refresh();});
$("search").addEventListener("input",refresh);
$("file-input").addEventListener("change",async e=>{try{await importFile(e.target.files[0]);}catch(err){message("No se pudo importar: "+err.message,true);}finally{e.target.value="";}});
$("hero-import").addEventListener("click",()=>$("file-input").click());
$("menu").addEventListener("click",()=>$("sport-nav").closest(".sidebar").classList.toggle("open"));
renderSports();refresh();
