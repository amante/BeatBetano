"use strict";
(function(){
 if(typeof window==="undefined"||typeof document==="undefined"||new URLSearchParams(location.search).get("sport")!=="nba")return;
 const stamp=value=>typeof value==="string"&&Number.isFinite(Date.parse(value));
 const validProp=prop=>prop&&prop.eligible===true&&prop.status==="eligible_for_user_review"
  &&prop.line_provider==="rotowire"&&stamp(prop.line_observed_at_utc)
  &&["points","rebounds","assists","pra"].includes(prop.market)
  &&["over","under"].includes(prop.direction)&&Number.isFinite(prop.line)
  &&Number.isInteger(prop.opponent_defense_rank)&&prop.opponent_defense_rank>=26&&prop.opponent_defense_rank<=30
  &&prop.season&&prop.season.games>=10&&prop.season.rate>=.9
  &&prop.matchup&&prop.matchup.games>=5&&prop.matchup.rate>=.9;
 const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
 function render(report){
  if(!report||report.kind!=="nba_informational_player_prop_signals_v1"||report.calibrated!==false
     ||report.model_probability_input!==false||report.parlay_generation!==false||!stamp(report.as_of_utc)
     ||!Array.isArray(report.games))return;
  const byId=new Map(report.games.map(game=>[String(game.game_id),game]));
  document.querySelectorAll(".nba-current-run__game[data-game-id]").forEach(card=>{
   card.querySelectorAll(".nba-player-prop-signal").forEach(node=>node.remove());
   const row=byId.get(card.dataset.gameId);if(!row||!stamp(row.tipoff_utc)||Date.parse(report.as_of_utc)>=Date.parse(row.tipoff_utc))return;
   const props=(Array.isArray(row.props)?row.props:[]).filter(validProp);if(!props.length)return;
   const detail=el("details",undefined,"nba-player-prop-signal");
   const summary=el("summary",undefined,"nba-player-prop-signal__summary");
   const icon=el("span","🎫","nba-player-prop-signal__icon");icon.setAttribute("role","img");icon.setAttribute("aria-label","Prop individual que cumple el filtro informativo; revísalo");
   summary.append(icon,el("span","Props individuales para revisar · "+props.length));detail.append(summary);
   for(const prop of props){
    const item=el("article",undefined,"nba-player-prop-signal__item");
    const market={points:"PTS",rebounds:"REB",assists:"AST",pra:"PRA"}[prop.market];
    item.append(el("strong",prop.player+" · "+market+" "+prop.direction+" "+prop.line));
    item.append(el("span","Uso #1 · defensa por posición #"+prop.opponent_defense_rank));
    item.append(el("span","Temporada "+prop.season.hits+"/"+prop.season.games+" ("+(prop.season.rate*100).toFixed(0)+"%) · vs rival "+prop.matchup.hits+"/"+prop.matchup.games+" ("+(prop.matchup.rate*100).toFixed(0)+"%)"));
    const sources=el("div",undefined,"nba-player-prop-signal__sources");
    for(const [label,url] of [["Línea RotoWire",prop.line_source_url],["Uso",prop.usage_source_url],["Defensa por posición",prop.position_defense_source_url]]){
     if(typeof url!=="string"||!url.startsWith("https://"))continue;
     const link=el("a",label);link.href=url;link.target="_blank";link.rel="noopener noreferrer";sources.append(link);
    }
    if(sources.childNodes.length)item.append(sources);detail.append(item);
   }
   detail.append(el("p","Señal informativa para evaluación individual. No es recomendación, no crea combinadas ni modifica el pronóstico del partido."));
   card.append(detail);
  });
 }
 fetch("./data/nba-player-prop-signals-latest.json",{cache:"no-store"}).then(response=>{
  if(!response.ok)throw Error("Prop signal feed unavailable");return response.json();
 }).then(report=>{
  render(report);
  const root=document.getElementById("nba-results");
  if(root)new MutationObserver(()=>render(report)).observe(root,{childList:true,subtree:true});
 }).catch(()=>{});
})();
