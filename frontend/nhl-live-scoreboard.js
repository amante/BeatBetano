"use strict";
// Read-only official live data; never changes forecasts or persisted labels.
(function(){
 if(new URLSearchParams(location.search).get("sport")!=="nhl")return;
 let busy=false;
 const node=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
 function logo(code){const wrap=node("span");wrap.className="live-team";if(/^[A-Z]{3}$/.test(code)){const img=node("img");img.src="https://assets.nhle.com/logos/nhl/svg/"+code+"_light.svg";img.alt="";img.width=32;img.height=32;img.addEventListener("error",()=>img.remove());wrap.append(img);}wrap.append(node("strong",code));return wrap;}
 async function refresh(){
  if(busy||document.hidden)return;busy=true;
  const date=document.getElementById("daily-date")?.value;
  try{
   const source=await fetch("./data/nhl-live-scoreboard.json",{cache:"no-store"});if(!source.ok)throw Error();const snapshot=await source.json();
   const rows=[...document.querySelectorAll(".daily-match[data-nhl-id]")];
   await Promise.all(rows.map(async row=>{
    const home=row.dataset.home,away=row.dataset.away,id=row.dataset.nhlId;if(!/^\d{10}$/.test(id))return;
    let teams=row.querySelector(".live-match-teams");if(!teams){teams=node("span");teams.className="live-match-teams";teams.append(logo(away),node("span","—"),logo(home));row.querySelector(":scope > strong")?.replaceWith(teams);}
    let note=row.querySelector(".live-note");if(!note){note=node("small");note.className="live-note";row.append(note);}
    try{
     const game=snapshot.games?.[id];if(!game)throw Error();
     if(game.homeTeam?.abbrev!==home||game.awayTeam?.abbrev!==away||String(game.id)!==id)throw Error();
     if(date!==document.getElementById("daily-date")?.value||!row.isConnected)return;
     const state=game.gameState,live=["LIVE","CRIT"].includes(state),final=["OFF","FINAL"].includes(state);const period=game.periodDescriptor;
     const stage=period?.periodType==="OT"?"Prórroga":period?.periodType==="SO"?"Penales":period?.number?period.number+".º período":"Período no informado";
     row.querySelector(".daily-state").textContent=(live||final?game.awayTeam.score+" : "+game.homeTeam.score+" · ":"")+(final?"Final":live?(game.clock?.inIntermission?"Intermedio · ":"")+stage+(game.clock?.timeRemaining?" · "+game.clock.timeRemaining:""):"Por comenzar");
     const goals=game.summary?.scoring||[];const scorers=goals.flatMap(p=>(p.goals||[]).map(g=>{const name=g.name?.default||[g.firstName?.default,g.lastName?.default].filter(Boolean).join(" ");return name?name+" ("+(g.teamAbbrev?.default||g.teamAbbrev||"")+", "+(g.timeInPeriod||"")+")":null;})).filter(Boolean);
     note.textContent=(scorers.length?"Goles: "+scorers.join(" · ")+". ":live?"Goleadores aún no informados. ":"")+"Actualizado "+new Date(snapshot.as_of_utc).toLocaleTimeString("es-CL",{timeZone:"America/Santiago"});
    }catch{note.textContent="Marcador en vivo no disponible; se conserva la última información del calendario.";}
   }));
  }catch{for(const row of document.querySelectorAll(".daily-match[data-nhl-id]")){let note=row.querySelector(".live-note");if(!note){note=node("small");note.className="live-note";row.append(note);}note.textContent="Actualización en vivo no disponible; información del calendario.";}}finally{busy=false;}
 }
 document.addEventListener("pulso:date-change",()=>setTimeout(refresh,100));setInterval(refresh,30000);setTimeout(refresh,1500);
})();
