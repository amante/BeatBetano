"use strict";
(function(){
 const sport=new URLSearchParams(location.search).get("sport")||"";
 const names={
  nhl:{ANA:"Anaheim Ducks",BOS:"Boston Bruins",BUF:"Buffalo Sabres",CAR:"Carolina Hurricanes",CBJ:"Columbus Blue Jackets",CGY:"Calgary Flames",CHI:"Chicago Blackhawks",COL:"Colorado Avalanche",DAL:"Dallas Stars",DET:"Detroit Red Wings",EDM:"Edmonton Oilers",FLA:"Florida Panthers",LAK:"Los Angeles Kings",MIN:"Minnesota Wild",MTL:"Montreal Canadiens",NJD:"New Jersey Devils",NSH:"Nashville Predators",NYI:"New York Islanders",NYR:"New York Rangers",OTT:"Ottawa Senators",PHI:"Philadelphia Flyers",PIT:"Pittsburgh Penguins",SEA:"Seattle Kraken",SJS:"San Jose Sharks",STL:"St. Louis Blues",TBL:"Tampa Bay Lightning",TOR:"Toronto Maple Leafs",UTA:"Utah Mammoth",VAN:"Vancouver Canucks",VGK:"Vegas Golden Knights",WPG:"Winnipeg Jets",WSH:"Washington Capitals"},
  nba:{ATL:"Atlanta Hawks",BOS:"Boston Celtics",BKN:"Brooklyn Nets",CHA:"Charlotte Hornets",CHI:"Chicago Bulls",CLE:"Cleveland Cavaliers",DAL:"Dallas Mavericks",DEN:"Denver Nuggets",DET:"Detroit Pistons",GSW:"Golden State Warriors",HOU:"Houston Rockets",IND:"Indiana Pacers",LAC:"LA Clippers",LAL:"Los Angeles Lakers",MEM:"Memphis Grizzlies",MIA:"Miami Heat",MIL:"Milwaukee Bucks",MIN:"Minnesota Timberwolves",NOP:"New Orleans Pelicans",NYK:"New York Knicks",OKC:"Oklahoma City Thunder",ORL:"Orlando Magic",PHI:"Philadelphia 76ers",PHX:"Phoenix Suns",POR:"Portland Trail Blazers",SAC:"Sacramento Kings",SAS:"San Antonio Spurs",TOR:"Toronto Raptors",UTA:"Utah Jazz",WAS:"Washington Wizards"},
  nfl:{ARI:"Arizona Cardinals",ATL:"Atlanta Falcons",BAL:"Baltimore Ravens",BUF:"Buffalo Bills",CAR:"Carolina Panthers",CHI:"Chicago Bears",CIN:"Cincinnati Bengals",CLE:"Cleveland Browns",DAL:"Dallas Cowboys",DEN:"Denver Broncos",DET:"Detroit Lions",GB:"Green Bay Packers",HOU:"Houston Texans",IND:"Indianapolis Colts",JAX:"Jacksonville Jaguars",KC:"Kansas City Chiefs",LV:"Las Vegas Raiders",LAC:"Los Angeles Chargers",LAR:"Los Angeles Rams",MIA:"Miami Dolphins",MIN:"Minnesota Vikings",NE:"New England Patriots",NO:"New Orleans Saints",NYG:"New York Giants",NYJ:"New York Jets",PHI:"Philadelphia Eagles",PIT:"Pittsburgh Steelers",SF:"San Francisco 49ers",SEA:"Seattle Seahawks",TB:"Tampa Bay Buccaneers",TEN:"Tennessee Titans",WAS:"Washington Commanders"}
 };
 const nhlCodes=new Set(Object.keys(names.nhl));
 const nbaIds={ATL:1610612737,BOS:1610612738,BKN:1610612751,CHA:1610612766,CHI:1610612741,CLE:1610612739,DAL:1610612742,DEN:1610612743,DET:1610612765,GSW:1610612744,HOU:1610612745,IND:1610612754,LAC:1610612746,LAL:1610612747,MEM:1610612763,MIA:1610612748,MIL:1610612749,MIN:1610612750,NOP:1610612740,NYK:1610612752,OKC:1610612760,ORL:1610612753,PHI:1610612755,PHX:1610612756,POR:1610612757,SAC:1610612758,SAS:1610612759,TOR:1610612761,UTA:1610612762,WAS:1610612764};
 const nameFor=code=>(names[sport]&&names[sport][code])||null;
 const svgNS="http://www.w3.org/2000/svg";
 function addIcon(holder,type){
  if(!holder||holder.querySelector("svg"))return;
  const paths={overview:[["path",{d:"m3 10 9-7 9 7"}],["path",{d:"M5 9v11h14V9"}],["path",{d:"M9 20v-6h6v6"}]],games:[["rect",{x:"3",y:"4",width:"18",height:"17",rx:"2"}],["path",{d:"M8 2v4m8-4v4M3 9h18"}]],calibration:[["circle",{cx:"12",cy:"12",r:"9"}],["path",{d:"M12 7v5l3 2"}]],sport:[["path",{d:"M5 5h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z"}],["path",{d:"M8 9h.01M16 15h.01M12 8v8m-4-4h8"}]]};
  const svg=document.createElementNS(svgNS,"svg");svg.setAttribute("viewBox","0 0 24 24");svg.setAttribute("aria-hidden","true");
  for(const [tag,attrs] of paths[type]||paths.sport){const node=document.createElementNS(svgNS,tag);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,v);svg.append(node)}
  holder.replaceChildren(svg);
 }
 function setupIcons(){
  document.querySelectorAll('.nav[data-nav="overview"] span').forEach(x=>addIcon(x,"overview"));
  document.querySelectorAll('.nav[data-nav="games"] span').forEach(x=>addIcon(x,"games"));
  document.querySelectorAll('.nav[data-nav="calibration"] span').forEach(x=>addIcon(x,"calibration"));
  document.querySelectorAll("#sport-nav .nav:not([data-nav])").forEach(nav=>{const icon=document.createElement("span");icon.setAttribute("aria-hidden","true");addIcon(icon,"sport");nav.prepend(icon)});
 }
 function logoFor(code){
  if(sport==="nhl"&&nhlCodes.has(code))return "https://assets.nhle.com/logos/nhl/svg/"+code+"_light.svg";
  if(sport==="nba"&&nbaIds[code])return "https://cdn.nba.com/logos/nba/"+nbaIds[code]+"/global/L/logo.svg";
  return "";
 }
 function teamNode(code){
  const chip=document.createElement("span");chip.className="pulso-team";
  const src=logoFor(code);
  if(src){const img=document.createElement("img");img.className="pulso-team-mark";img.src=src;img.alt="";img.loading="lazy";img.addEventListener("error",()=>img.remove(),{once:true});chip.append(img)}
  else {const mark=document.createElement("span");mark.className="pulso-team-mark pulso-team-fallback";mark.textContent=code;mark.setAttribute("aria-hidden","true");chip.append(mark)}
  const label=document.createElement("span");label.className="pulso-team-name";label.textContent=nameFor(code)||code;chip.append(label);return chip;
 }
 function decoratePair(el){
  if(!el||el.dataset.pulsoTeamsDone)return;
  const match=el.textContent.trim().match(/^([A-Z]{2,4})\s+[—-]\s+([A-Z]{2,4})$/);
  if(!match||!nameFor(match[1])||!nameFor(match[2]))return;
  el.dataset.pulsoTeamsDone="true";el.replaceChildren(teamNode(match[1]));
  const vs=document.createElement("span");vs.className="pulso-versus";vs.textContent="vs";el.append(vs,teamNode(match[2]));
 }
 function translateCodes(root){
  if(!root)return;
  const map=names[sport];if(!map)return;
  const keys=Object.keys(map).sort((a,b)=>b.length-a.length);
  const re=new RegExp("(^|[^A-Z0-9])("+keys.join("|")+")(?=$|[^A-Z0-9])","g");
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
  const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
  for(const node of nodes){if(node.parentElement?.closest("script,style,svg,.pulso-team"))continue;node.nodeValue=node.nodeValue.replace(re,(all,prefix,code)=>prefix+map[code]);}
 }
 function teamPass(root=document){
  root.querySelectorAll?.(".daily-match strong, #daily-results h3, #nba-rotation-pilot h3, .forecast-card h3, .nhl-postmortem-game h3").forEach(decoratePair);
  root.querySelectorAll?.(".daily-match, #daily-results, #progressive-forecasts, #nba-rotation-pilot, #nhl-five-market, #nhl-joint-model, #pulso-nhl-research").forEach(translateCodes);
 }
 function titleFor(panel){
  const h=panel.querySelector("h2,h3,h4")?.textContent?.trim();
  if(h)return h;
  return panel.getAttribute("aria-label")||"Análisis complementario";
 }
 function wrapAccordion(target,label,cls){
  if(!target||target.closest("details.pulso-inline-accordion,details.pulso-accordion"))return null;
  const details=document.createElement("details");details.className=cls||"pulso-inline-accordion";
  const summary=document.createElement("summary");summary.textContent=label;details.append(summary);
  target.parentNode.insertBefore(details,target);details.append(target);return details;
 }
 function setupAccordions(){
  const history=document.querySelector(".daily-yesterday");
  if(history&&!history.closest("details"))wrapAccordion(history,"Resultados anteriores");
  const main=document.querySelector("main");if(!main)return;
  let bucket=document.getElementById("pulso-more-analysis");
  if(!bucket){
   bucket=document.createElement("details");bucket.id="pulso-more-analysis";bucket.className="pulso-accordion";
   const summary=document.createElement("summary");summary.append(document.createTextNode("Más análisis y herramientas"));
   const hint=document.createElement("small");hint.textContent="Abrir secciones complementarias";summary.append(hint);
   const content=document.createElement("div");content.className="pulso-accordion-content";bucket.append(summary,content);
   const anchor=document.getElementById("daily-panel")||main.lastElementChild;anchor.insertAdjacentElement("afterend",bucket);
  }
  const content=bucket.querySelector(".pulso-accordion-content");
  [...main.children].forEach(node=>{
   if(node===bucket||node.id==="daily-panel"||node.id==="progressive-forecasts"||node.id==="nba-runner"||node.id==="messages"||!node.matches(".panel,.forecast-panel"))return;
   content.append(node);
  });
  bucket.hidden=!content.children.length;
 }
 function setup(){
  setupIcons();setupAccordions();teamPass();
  const main=document.querySelector("main");if(!main)return;
  let queued=false;
  const observer=new MutationObserver(records=>{
   if(queued)return;queued=true;
   requestAnimationFrame(()=>{queued=false;setupAccordions();teamPass();});
  });
  observer.observe(main,{childList:true,subtree:true,characterData:true});
 }
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",setup,{once:true});else setup();
})();