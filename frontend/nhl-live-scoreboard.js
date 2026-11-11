"use strict";
// Read-only official live data; never changes forecasts or persisted labels.
(function(){
 if(new URLSearchParams(location.search).get("sport")!=="nhl")return;
 let busy=false;
 const node=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
 async function refresh(){
  if(busy||document.hidden)return;busy=true;
  const date=document.getElementById("daily-date")?.value;
  try{
   const configResponse=await fetch("./data/runtime-config.json",{cache:"no-store"});const config=configResponse.ok?await configResponse.json():{};
   const endpoint=config.nhlScoreboardEndpoint;
   const rows=[...document.querySelectorAll(".daily-match[data-nhl-id]")];
   await Promise.all(rows.map(async row=>{
    const home=row.dataset.home,away=row.dataset.away,id=row.dataset.nhlId;if(!/^\d{10}$/.test(id))return;
    const stateNode=row.querySelector(".daily-state");if(!stateNode)return;
    let note=row.querySelector(".live-note");if(!note){note=node("small");note.className="live-note";row.append(note);}
    try{
     if(!endpoint)throw Error();const url=new URL(endpoint);if(url.protocol!=="https:")throw Error();url.searchParams.set("game",id);const response=await fetch(url,{cache:"no-store",signal:AbortSignal.timeout(10000)});if(!response.ok)throw Error();const game=await response.json();
     if(game.homeTeam?.abbrev!==home||game.awayTeam?.abbrev!==away||String(game.id)!==id)throw Error();
     if(date!==document.getElementById("daily-date")?.value||!row.isConnected)return;
     const state=game.gameState,live=["LIVE","CRIT"].includes(state),final=["OFF","FINAL"].includes(state);const period=game.periodDescriptor;
     const stage=period?.periodType==="OT"?"Prórroga":period?.periodType==="SO"?"Penales":period?.number?period.number+".º período":"Período no informado";
     stateNode.classList.toggle("is-live",live);stateNode.classList.toggle("is-final",final);
     stateNode.textContent=(live||final?game.awayTeam.score+" : "+game.homeTeam.score+" · ":"")+(final?"Final":live?(game.clock?.inIntermission?"Intermedio · ":"")+stage+(game.clock?.timeRemaining?" · "+game.clock.timeRemaining:""):"Por comenzar");
     const goals=game.summary?.scoring||[];const scorers=goals.flatMap(p=>(p.goals||[]).map(g=>{const name=g.name?.default||[g.firstName?.default,g.lastName?.default].filter(Boolean).join(" ");return name?name+" ("+(g.teamAbbrev?.default||g.teamAbbrev||"")+", "+(g.timeInPeriod||"")+")":null;})).filter(Boolean);
     note.textContent=(scorers.length?"Goles: "+scorers.join(" · ")+". ":live?"Goleadores aún no informados. ":"")+"Actualizado "+new Date().toLocaleTimeString("es-CL",{timeZone:"America/Santiago"});
    }catch{note.textContent="Marcador en vivo no disponible; se conserva la última información del calendario.";}
   }));
  }catch{for(const row of document.querySelectorAll(".daily-match[data-nhl-id]")){let note=row.querySelector(".live-note");if(!note){note=node("small");note.className="live-note";row.append(note);}note.textContent="Actualización en vivo no disponible; información del calendario.";}}finally{busy=false;}
 }
 document.addEventListener("pulso:date-change",()=>setTimeout(refresh,100));setTimeout(refresh,1500);
})();
