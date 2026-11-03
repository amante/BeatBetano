"use strict";
(async function(){
 if(new URLSearchParams(location.search).get("sport")!=="nba")return;
 const root=document.createElement("section");root.className="panel";document.querySelector("main").prepend(root);
 const el=(tag,text)=>{const x=document.createElement(tag);x.textContent=text;return x;};let data;
 function render(){root.replaceChildren(el("h2","Pronósticos NBA"));
  if(!data){root.append(el("p","Todavía no hay una emisión NBA publicada."));return;}
  const day=document.getElementById("daily-date").value;
  const rows=data.predictions.filter(r=>new Intl.DateTimeFormat("en-CA",{timeZone:"America/Santiago",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(r.tipoff_utc))===day);
  root.append(el("p","Experimental · historial de resultados; sin ajustes de lesiones o alineaciones. No calibrado."));
  root.append(el("p","Emisión: "+new Date(data.created_at_utc).toLocaleString("es-CL",{timeZone:"America/Santiago"})));
  if(!rows.length)root.append(el("p","No hay pronósticos en esta emisión para la fecha elegida."));
  for(const row of rows){const card=el("article","");card.append(el("h3",row.away_team+" — "+row.home_team));
   card.append(el("p",new Date(row.tipoff_utc).toLocaleString("es-CL",{timeZone:"America/Santiago"})+" · "+(Date.now()>=Date.parse(row.tipoff_utc)?"Pronóstico previo al inicio":"Por comenzar")));
   for(const [name,key] of [["Elo","elo_p_home"],["Challenger","challenger_p_home"],["Híbrido","hybrid_p_home"]])card.append(el("p",name+": "+row.away_team+" "+((1-row[key])*100).toFixed(1)+"% · "+row.home_team+" "+(row[key]*100).toFixed(1)+"%"));root.append(card);}
 }
 document.getElementById("daily-date").addEventListener("change",render);render();
 try{const response=await fetch("./data/nba-predictions-latest.json",{cache:"no-store"});if(!response.ok)throw Error();const x=await response.json();if(x.kind!=="nba_pulso_research_publication_v1"||!Array.isArray(x.predictions))throw Error();for(const r of x.predictions){if(Date.parse(x.created_at_utc)>=Date.parse(r.tipoff_utc)||[r.elo_p_home,r.challenger_p_home,r.hybrid_p_home].some(p=>!Number.isFinite(p)||p<=0||p>=1))throw Error();}data=x;render();}catch{render();}
})();
