const test=require('node:test');const assert=require('node:assert/strict');
const {validate,forDay,stale}=require('../nba-predictions.js');
const packet=()=>({kind:'nba_forward_publication_v2',as_of_utc:'2026-11-05T04:00:00Z',last_source_capture_utc:'2026-11-05T03:00:00Z',performance_metrics:null,sporting_adjustment_applied:false,evaluation_status:'window_open_metrics_withheld',source_error_count:0,sporting_evidence_errors:[],calendar_date_coverage_chile:{'2026-11-05':false},games:[{game_id:'1',home_team:'BOS',away_team:'MIL',tipoff_utc:'2026-11-05T02:00:00Z',source_state:'in',status:'paired_pregame_emission',issues:[],outcome:null,sporting:{BOS:null,MIL:null},first_prediction:{game_id:'1',home_team:'BOS',away_team:'MIL',tipoff_utc:'2026-11-05T02:00:00Z',prediction_as_of_utc:'2026-11-04T20:00:00Z',elo_p_home:.6,challenger_p_home:.65}}]});
test('publication keeps original per-game timestamp, both MLs and Chile date',()=>{const p=packet();assert.equal(validate(p),true);assert.equal(forDay(p,'2026-11-04').length,1);assert.equal(forDay(p,'2026-11-05').length,0);assert.equal(stale(p,Date.parse('2026-11-05T12:00:00Z')),true);});
test('duplicates, invalid probabilities, post-start emission and interim metrics fail closed',()=>{for(const mutate of [p=>p.games.push(p.games[0]),p=>p.games[0].first_prediction.elo_p_home=NaN,p=>p.games[0].first_prediction.prediction_as_of_utc=p.games[0].tipoff_utc,p=>p.performance_metrics={brier:.2}]){const p=packet();mutate(p);assert.equal(validate(p),false);}});
async function render(p,date='2026-11-04',ok=true){
 const fs=require('node:fs'),vm=require('node:vm');
 function element(tag){return {tag,textContent:'',children:[],append(...x){this.children.push(...x)},prepend(...x){this.children.unshift(...x)},replaceChildren(...x){this.children=x},addEventListener(){}};}
 const main=element('main'),picker={value:date,addEventListener(){}};
 const document={createElement:element,querySelector:()=>main,getElementById:()=>picker};const window={};
 vm.runInNewContext(fs.readFileSync(require.resolve('../nba-predictions.js'),'utf8'),{window,document,location:{search:'?sport=nba'},URLSearchParams,Intl,Date,fetch:async()=>({ok,json:async()=>p})});
 await window.PulsoNbaForward.ready;
 const text=n=>[n.textContent||'',...(n.children||[]).map(text)].join(' ');return text(main);
}
test('render includes per-game original ML and explicit unsupported sporting/+20 status',async()=>{const text=await render(packet());assert.match(text,/MIL 40\.0% · BOS 60\.0%/);assert.match(text,/MIL 35\.0% · BOS 65\.0%/);assert.match(text,/ventaja \+20: PASS/);assert.doesNotMatch(text,/Híbrido/);});
test('uncovered date differs from no games, and fetch failure never falls back to stale percentages',async()=>{assert.match(await render(packet(),'2026-11-05'),/no tiene cobertura suficiente/);const text=await render(packet(),'2026-11-04',false);assert.match(text,/No se pudo cargar/);assert.doesNotMatch(text,/60\.0%/);});
test('missing paired emission is PASS, changed fixtures hide unsupported percentages',async()=>{let p=packet();p.games[0].first_prediction=null;assert.match(await render(p),/No hay una pareja/);p=packet();p.games[0].issues=['fixture_tipoff_utc_changed'];const text=await render(p);assert.match(text,/requiere revisión/);assert.doesNotMatch(text,/60\.0%/);});
