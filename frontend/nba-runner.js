"use strict";
(function(){
 if(new URLSearchParams(location.search).get("sport")!=="nba")return;
 const root=document.getElementById("nba-runner");
 if(!root)return;
 const el=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
 const button=el("button","Generar predicción NBA de hoy","primary");
 button.type="button";button.disabled=true;
 const status=el("p","Conectando con el servicio protegido…","nba-run-status");
 status.setAttribute("role","status");status.setAttribute("aria-live","polite");
 root.hidden=false;
 root.append(el("div","ACTUALIZACIÓN MANUAL","eyebrow"),el("h2","Ejecutar modelo NBA"),
  el("p","Captura el calendario y el informe oficial de lesiones disponibles ahora. La corrida publica la nueva captura en PULSO; puede tardar unos minutos.","nba-run-note"),button,status);
 const localDay=()=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
 let endpoint=null,origin=null;
 fetch("./data/runtime-config.json",{cache:"no-store"}).then(response=>{
  if(!response.ok)throw new Error("config");return response.json();
 }).then(config=>{
  const candidate=new URL(config.nba_simulation_endpoint||"",location.href);
  const expected=config.simulation_endpoint_origin||"";
  if(candidate.protocol!=="https:"||candidate.origin!==expected||candidate.pathname!=="/api/nba/run"||candidate.username||candidate.password||candidate.search||candidate.hash)
   throw new Error("endpoint");
  endpoint=candidate;origin=expected;button.disabled=false;status.textContent="Listo para iniciar una corrida protegida.";
 }).catch(()=>{status.textContent="Ejecución protegida no configurada. Usa la corrida manual de GitHub Actions.";});
 button.addEventListener("click",async()=>{
  if(!endpoint||endpoint.origin!==origin)return;
  const selected=document.getElementById("daily-date")?.value;
  if(selected&&selected!==localDay()){status.textContent="La corrida manual genera la captura de hoy, según la fecha de Chile.";return;}
  button.disabled=true;status.textContent="Solicitando corrida protegida…";
  let accepted=false;
  try{
   const response=await fetch(endpoint,{method:"POST",headers:{"Content-Type":"application/json"},credentials:"include",redirect:"error",body:JSON.stringify({sport:"nba",date:localDay()})});
   if(response.status===401||response.status===403)throw new Error("Inicia sesión en Cloudflare Access");
   if(!response.ok)throw new Error("El servicio respondió HTTP "+response.status);
   if(!(response.headers.get("Content-Type")||"").includes("application/json"))throw new Error("No se recibió confirmación JSON");
   const data=await response.json();
   if(!data.accepted)throw new Error("No se confirmó la solicitud");
   accepted=true;
   status.textContent="Corrida aceptada por GitHub Actions; aún se está procesando. ";
   const link=el("a","Ver estado de la corrida");link.href=data.workflow_url;link.target="_blank";link.rel="noopener noreferrer";status.append(link);
  }catch(error){
   status.textContent="No se confirmó la ejecución. "+error.message+". Comprueba GitHub Actions antes de volver a intentarlo. ";
   const link=el("a","Iniciar sesión en Cloudflare Access");link.href=endpoint.href;link.target="_blank";link.rel="noopener noreferrer";status.append(link);
  }finally{button.disabled=accepted;}
 });
})();
