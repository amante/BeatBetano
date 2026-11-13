const test=require('node:test'),assert=require('node:assert/strict');
const {validate,forDay}=require('../progressive-forecasts.js');
function packet(sport='nfl'){
 const revision=(i,home)=>({revision:i,snapshot_sha256:'a'.repeat(64),cutoff_utc:`2026-11-06T${i===1?'10':'11'}:00:00Z`,emitted_at_utc:`2026-11-06T${i===1?'10':'11'}:01:00Z`,start_utc:'2026-11-07T00:00:00Z',stage:i===1?'initial':'update',model_version:'baseline-v1',probabilities:sport==='soccer'?{home,draw:.2,away:.8-home}:{home,away:1-home},assumptions:['Expected rotation'],unresolved_inputs:['Starting lineup'],selection_status:'PASS',calibration_certified:false});
 const first=revision(1,.55),last=revision(2,.6);
 return {kind:'progressive_forecast_index',generated_at_utc:'2026-11-06T12:00:00Z',errors:[],events:[{sport,event_id:'1',participants:['BOS','MIL'],start_utc:last.start_utc,initial:first,latest:last,history:[first,last],delta:Object.fromEntries(Object.keys(first.probabilities).map(k=>[k,last.probabilities[k]-first.probabilities[k]])),selection_status:'PASS',calibration_certified:false}]};
}
test('shared history supports five sports, Chile date and three-way soccer',()=>{
 for(const sport of ['nba','nfl','nhl','soccer','tennis']){const p=packet(sport);assert.equal(validate(p),true);assert.equal(forDay(p,sport,'2026-11-06').length,1);assert.equal(forDay(p,sport,'2026-11-07').length,0);}
});
test('invalid percentages, deltas, chronological history and duplicate events rejected',()=>{
 for(const mutate of [p=>p.events[0].latest.probabilities.home=NaN,p=>p.events[0].delta.home=.9,p=>p.events[0].latest.emitted_at_utc=p.events[0].start_utc,p=>p.events.push(p.events[0]),p=>p.events[0].history.reverse()]){const p=packet();mutate(p);assert.equal(validate(p),false);}
});
async function render(p,{sport='nfl',ok=true,date='2026-11-06'}={}){
 const fs=require('node:fs'),vm=require('node:vm');
 function element(tag){return {tag,textContent:'',children:[],setAttribute(){},append(...x){this.children.push(...x)},replaceChildren(...x){this.children=x},addEventListener(){}};}
 const root=element('section'),picker={value:date,addEventListener(){}};
 const window={},document={getElementById:id=>id==='progressive-forecasts'?root:id==='daily-date'?picker:null,createElement:element};
 vm.runInNewContext(fs.readFileSync(require.resolve('../progressive-forecasts.js'),'utf8'),{window,document,location:{search:'?sport='+sport},URLSearchParams,Intl,Date,fetch:async()=>({ok,json:async()=>p})});
 await window.PulsoProgressiveForecasts.ready;
 const text=e=>[e.textContent,...e.children.map(text)].join(' ');return text(root);
}
function nbaPublication(){
 return {kind:'nba_pulso_research_publication_v1',run_id:'200',snapshot_sha256:'b'.repeat(64),created_at_utc:'2026-11-13T15:17:50Z',predictions:[{
  game_id:'401909296',away_team:'NY',home_team:'IND',tipoff_utc:'2026-11-14T00:00:00Z',statistical_baseline_p_home:.246,model_p_home:.250,probability_adjustments_applied:['travel'],
  travel_probability_scenario:{status:'research_scenario',applied:true},injury_probability_scenario:{status:'blocked',reason:'IND:no_official_report_row_for_team;NY:no_official_report_row_for_team'},
  player_matchup_probability_scenario:{status:'blocked',reason:'head_to_head_matchup_source_unavailable'},
  player_stat_projections:{teams:{IND:{players:[{player:'Example Player',projection_status:'estimated',points_projection:10.2,rebounds_projection:4.1,assists_projection:2.3}]},NY:{players:[]}}}
 }]};
}
test('NBA page renders the latest automatic run and clearly reports applied or blocked modules',async()=>{
 const text=await render(nbaPublication(),{sport:'nba',date:'2026-11-13'});
 assert.match(text,/Corrida automática #200/);assert.match(text,/Indiana Pacers/);assert.match(text,/New York Knicks/);
 assert.match(text,/Viajes y zona horaria · sí ajustó/);assert.match(text,/Lesiones · Sin filas oficiales/);
 assert.match(text,/Cruces de jugadores · Sin datos históricos/);assert.match(text,/Example Player/);assert.match(text,/sin calibración certificada/);
});
test('renders initial, latest, delta, assumptions and complete revision history',async()=>{
 const text=await render(packet());assert.match(text,/55,0 %/);assert.match(text,/60,0 %/);assert.match(text,/\+5,0 p.p./);assert.match(text,/Starting lineup/);assert.match(text,/#1/);assert.match(text,/#2/);assert.match(text,/calibración no certificada/);
});
test('unchanged probability is explicit and error never shows old percentages',async()=>{
 const p=packet();p.events[0].latest.probabilities={...p.events[0].initial.probabilities};p.events[0].delta={home:0,away:0};assert.match(await render(p),/Sin cambio/);
 const failed=await render(packet(),{ok:false});assert.match(failed,/No se pudieron cargar/);assert.doesNotMatch(failed,/60,0 %/);
});
test('sports and selected dates remain isolated; empty data does not invent a forecast',async()=>{
 const text=await render(packet(),{sport:'nhl'});assert.match(text,/No hay pronósticos archivados/);assert.doesNotMatch(text,/60,0 %/);
 assert.match(await render(packet(),{date:'2026-11-07'}),/No hay pronósticos archivados/);
 const soccer=await render(packet('soccer'),{sport:'soccer'});assert.match(soccer,/Empate/);assert.match(soccer,/90 minutos/);
});
