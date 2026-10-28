"use strict";
const $=id=>document.getElementById(id);
const overlay=$("login-overlay"),hub=$("hub");
let priorFocus=null;
function openLogin(){priorFocus=document.activeElement;overlay.classList.remove("hidden");$("close-login").focus();}
function closeLogin(){overlay.classList.add("hidden");if(priorFocus)priorFocus.focus();}
function enterDemo(){closeLogin();document.querySelector(".landing").classList.add("hidden");hub.classList.remove("hidden");hub.scrollIntoView({behavior:"smooth"});$("hub-title").focus?.();}
$("open-login").addEventListener("click",openLogin);
$("hero-login").addEventListener("click",openLogin);
$("close-login").addEventListener("click",closeLogin);
$("demo-login").addEventListener("click",enterDemo);
$("leave-demo").addEventListener("click",()=>{hub.classList.add("hidden");document.querySelector(".landing").classList.remove("hidden");window.scrollTo({top:0,behavior:"smooth"});});
overlay.addEventListener("click",e=>{if(e.target===overlay)closeLogin();});
document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!overlay.classList.contains("hidden"))closeLogin();});
