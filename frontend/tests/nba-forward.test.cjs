const test=require('node:test');const assert=require('node:assert/strict');
const {validate,forDay,stale}=require('../nba-predictions.js');
const packet=()=>({kind:'nba_forward_publication_v2',as_of_utc:'2026-11-05T04:00:00Z',last_source_capture_utc:'2026-11-05T03:00:00Z',performance_metrics:null,sporting_adjustment_applied:false,evaluation_status:'window_open_metrics_withheld',source_error_count:0,sporting_evidence_errors:[],calendar_date_coverage_chile:{'2026-11-05':false},games:[{game_id:'1',home_team:'BOS',away_team:'MIL',tipoff_utc:'2026-11-05T02:00:00Z',source_state:'in',status:'paired_pregame_emission',issues:[],outcome:null,sporting:{BOS:null,MIL:null},first_prediction:{game_id:'1',home_team:'BOS',away_team:'MIL',tipoff_utc:'2026-11-05T02:00:00Z',prediction_as_of_utc:'2026-11-04T20:00:00Z',elo_p_home:.6,challenger_p_home:.65}}]});
test('publication keeps original per-game timestamp, both MLs and Chile date',()=>{const p=packet();assert.equal(validate(p),true);assert.equal(forDay(p,'2026-11-04').length,1);assert.equal(forDay(p,'2026-11-05').length,0);assert.equal(stale(p,Date.parse('2026-11-05T12:00:00Z')),true);});
test('duplicates, invalid probabilities, post-start emission and interim metrics fail closed',()=>{for(const mutate of [p=>p.games.push(p.games[0]),p=>p.games[0].first_prediction.elo_p_home=NaN,p=>p.games[0].first_prediction.prediction_as_of_utc=p.games[0].tipoff_utc,p=>p.performance_metrics={brier:.2}]){const p=packet();mutate(p);assert.equal(validate(p),false);}});
async function render(p,date='2026-11-04',ok=true){
 const fs=require('node:fs'),vm=require('node:vm');
 function element(tag){return {tag,style:{},textContent:'',children:[],append(...x){this.children.push(...x)},prepend(...x){this.children.unshift(...x)},replaceChildren(...x){this.children=x},addEventListener(){}};}
 const main=element('main'),picker={value:date,addEventListener(){}},agenda=element('div'),label=element('h2'),source=element('p');
 main.append(label,source,agenda);
 const document={createElement:element,querySelector:s=>s==='main'?main:null,getElementById:id=>({'daily-date':picker,'daily-results':agenda,'daily-label':label,'feed-message':source}[id]||null)};const window={};
 vm.runInNewContext(fs.readFileSync(require.resolve('../nba-predictions.js'),'utf8'),{window,document,location:{search:'?sport=nba'},URLSearchParams,Intl,Date,fetch:async()=>({ok,json:async()=>p})});
 await window.PulsoNbaForward.ready;
 const text=n=>[n.textContent||'',...(n.children||[]).map(text)].join(' ');return text(main);
}
test('render includes per-game original ML and explicit unsupported sporting/+20 status',async()=>{const text=await render(packet());assert.match(text,/Milwaukee Bucks 40\.0% · Boston Celtics 60\.0%/);assert.match(text,/Milwaukee Bucks 35\.0% · Boston Celtics 65\.0%/);assert.match(text,/ventaja \+20: PASS/);assert.doesNotMatch(text,/Híbrido/);});
test('uncovered date differs from no games, and fetch failure never falls back to stale percentages',async()=>{assert.match(await render(packet(),'2026-11-05'),/no tiene cobertura suficiente/);const text=await render(packet(),'2026-11-04',false);assert.match(text,/No se pudo cargar/);assert.doesNotMatch(text,/60\.0%/);});
test('missing paired emission is PASS, changed fixtures hide unsupported percentages',async()=>{let p=packet();p.games[0].first_prediction=null;assert.match(await render(p),/No hay una pareja/);p=packet();p.games[0].issues=['fixture_tipoff_utc_changed'];const text=await render(p);assert.match(text,/requiere revisión/);assert.doesNotMatch(text,/60\.0%/);});

test('agenda uses the same NBA cohort instead of a second empty shared feed',async()=>{const text=await render(packet());assert.match(text,/NBA · 2026-11-04 · 1 partido registrado/);assert.match(text,/Calendario y emisiones del registro NBA/);assert.doesNotMatch(text,/daily.json|0 partidos|panel NHL/);});
test('full NBA page skips legacy fetch, hides NHL/simulator/stats and keeps date changes aligned',async()=>{
 const fs=require('node:fs'),vm=require('node:vm');
 function el(){return {textContent:'',children:[],style:{},listeners:{},append(...x){this.children.push(...x)},prepend(...x){this.children.unshift(...x)},replaceChildren(...x){this.children=x},addEventListener(type,fn){(this.listeners[type]??=[]).push(fn)}};}
 const elements={};for(const id of ['daily-date','daily-results','daily-label','feed-message','daily-stats','simulation-status','run-simulation','crumb','sport-nav','menu','nhl-five-market','nhl-joint-model','pulso-nhl-research'])elements[id]=el();
 const main=el(),yesterday=el(),simulator=el();main.append(elements['daily-results']);
 const selectors={'main':main,'.daily-yesterday':yesterday,'.simulation-panel':simulator,'#daily-stats':elements['daily-stats'],'#nhl-five-market':elements['nhl-five-market'],'#nhl-joint-model':elements['nhl-joint-model'],'#pulso-nhl-research':elements['pulso-nhl-research']};
 const document={createElement:el,getElementById:id=>elements[id]||null,querySelector:s=>selectors[s]||null,querySelectorAll:()=>[]};
 const window={},urls=[],context=vm.createContext({window,document,location:{search:'?sport=nba'},URLSearchParams,Intl,Date,fetch:async url=>{urls.push(url);return {ok:true,json:async()=>packet()}}});
 vm.runInContext(fs.readFileSync(require.resolve('../daily.js'),'utf8'),context);
 vm.runInContext(fs.readFileSync(require.resolve('../nba-predictions.js'),'utf8'),context);
 await window.PulsoNbaForward.ready;
 assert.deepEqual(urls,['./data/certification-readiness-latest.json','./data/nba-forward-latest.json','./data/nba-predictions-latest.json']);
 for(const panel of [yesterday,simulator,elements['daily-stats'],elements['nhl-five-market'],elements['nhl-joint-model'],elements['pulso-nhl-research']])assert.equal(panel.hidden,true);
 elements['daily-date'].value='2026-11-04';for(const fn of elements['daily-date'].listeners.change)fn();
 assert.equal(elements['daily-label'].textContent,'NBA · 2026-11-04 · 1 partido registrado');
 assert.match(elements['feed-message'].textContent,/registro NBA/);
});

test('shared NHL markup belongs only to NHL across all five sport routes',()=>{
 const fs=require('node:fs'),vm=require('node:vm');
 const html=fs.readFileSync(require.resolve('../dashboard.html'),'utf8');
 for(const id of ['nhl-five-market','nhl-joint-model','pulso-nhl-research'])assert.match(html,new RegExp('id="'+id+'" data-sport-only="nhl" hidden'));
 for(const sport of ['nba','nfl','soccer','tennis','nhl']){
  const panels=[1,2,3].map(()=>({dataset:{sportOnly:'nhl'},style:{},hidden:true}));
  const element=()=>({textContent:'',append(){},addEventListener(){}});
  const elements={};const document={getElementById:id=>elements[id]??=element(),querySelectorAll:selector=>selector==='[data-sport-only]'?panels:[],createElement:element};
  const code=fs.readFileSync(require.resolve('../daily.js'),'utf8').replace(/\nload\(\);\s*$/,'');
  vm.runInNewContext(code,{document,location:{search:'?sport='+sport},URLSearchParams,Intl,Date});
  for(const panel of panels){assert.equal(panel.hidden,sport!=='nhl');assert.equal(panel.style.display,sport==='nhl'?'':'none');}
 }
});
