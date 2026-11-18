"use strict";
const $=id=>document.getElementById(id);
const overlay=$("login-overlay"),hub=$("hub");
const sportIconPaths={
 nba:[["circle",{cx:"12",cy:"12",r:"9"}],["path",{d:"M3.5 9h17M3.5 15h17M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"}]],
 nfl:[["path",{d:"M3 12c3-5 7-7 12-7 2 0 4 1 6 2-1 5-5 10-12 12-2 0-4-1-6-2 1-2 1-3 0-5Z"}],["path",{d:"m8 12 8 0m-6-2v4m3-4v4"}]],
 nhl:[["path",{d:"M4 15h15l-2 4H2l2-4Zm5-2 8-8m-2-2 5 5"}],["path",{d:"M7 15v4"}]],
 soccer:[["circle",{cx:"12",cy:"12",r:"9"}],["path",{d:"m12 7 3 2-1 4h-4L9 9l3-2Zm0-4v4m8 5-5-1m-11 0 5-1m-3 7 4-3m6 3-4-3"}]],
 tennis:[["circle",{cx:"12",cy:"12",r:"9"}],["path",{d:"M5 5c4 1 7 4 8 8s0 6-2 8M19 5c-4 1-7 4-8 8s0 6 2 8"}]]
};
const svgNS="http://www.w3.org/2000/svg";
function addSportIcon(holder,key){
 const svg=document.createElementNS(svgNS,"svg");svg.setAttribute("viewBox","0 0 24 24");svg.setAttribute("aria-hidden","true");svg.setAttribute("focusable","false");
 for(const [tag,attrs] of sportIconPaths[key]||sportIconPaths.nba){const shape=document.createElementNS(svgNS,tag);for(const [name,value] of Object.entries(attrs))shape.setAttribute(name,value);svg.append(shape)}
 holder.replaceChildren(svg);
}
document.querySelectorAll("[data-sport-icon]").forEach(holder=>addSportIcon(holder,holder.dataset.sportIcon));
let priorFocus=null;
function openLogin(){priorFocus=document.activeElement;overlay.classList.remove("hidden");$("close-login").focus();}
function closeLogin(){overlay.classList.add("hidden");if(priorFocus)priorFocus.focus();}
function enterDemo(){closeLogin();document.querySelector(".landing").classList.add("hidden");hub.classList.remove("hidden");hub.scrollIntoView({behavior:"smooth"});$("hub-title").focus();}
$("open-login").addEventListener("click",openLogin);
$("hero-login").addEventListener("click",openLogin);
$("close-login").addEventListener("click",closeLogin);
$("demo-login").addEventListener("click",enterDemo);
$("leave-demo").addEventListener("click",()=>{hub.classList.add("hidden");document.querySelector(".landing").classList.remove("hidden");window.scrollTo({top:0,behavior:"smooth"});$("hero-login").focus();});
overlay.addEventListener("click",e=>{if(e.target===overlay)closeLogin();});
document.addEventListener("keydown",e=>{
 if(overlay.classList.contains("hidden"))return;
 if(e.key==="Escape"){closeLogin();return;}
 if(e.key!=="Tab")return;
 const focusable=[...overlay.querySelectorAll('button:not([disabled]),a[href],[tabindex]:not([tabindex="-1"])')].filter(el=>el.getClientRects().length);
 if(!focusable.length){e.preventDefault();return;}
 const first=focusable[0],last=focusable[focusable.length-1];
 if(e.shiftKey&&(document.activeElement===first||!overlay.contains(document.activeElement))){e.preventDefault();last.focus();}
 else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
});
