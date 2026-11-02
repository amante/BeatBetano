const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('frontend/daily.js','utf8');
// Stable fixtures: publication must not depend on today's live game states.
const sampleSlate=()=>({kind:'nhl_daily_complete_slate_274',date:'2026-11-02',schedule_captured_at:'2026-11-02T00:00:00Z',games:[
 {game_id:'2026020232',home:'BOS',away:'VGK',start_utc:'2026-11-03T00:00:00Z',game_state_at_capture:'OFF'},
 {game_id:'2026020233',home:'FLA',away:'DET',start_utc:'2026-11-03T00:00:00Z',game_state_at_capture:'FUT'}
]});
function harness(response){
 const element=()=>({value:'',textContent:'',children:[],append(...items){this.children.push(...items);this.link=items.at(-1);},replaceChildren(...items){this.children=items;},addEventListener(){}});
 const nodes=new Map();const node=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);};
 const calls=[];const context=vm.createContext({URL,URLSearchParams,Intl,Date,Set,Map,CustomEvent:class{constructor(type,{detail}){this.type=type;this.detail=detail;}},location:{search:'?sport=nhl',href:'https://amante.github.io/BeatBetano/dashboard.html',origin:'https://amante.github.io'},document:{getElementById:node,querySelector:()=>({value:'all'}),querySelectorAll:()=>[],dispatchEvent:event=>calls.push({event}),createElement:element},fetch:async(url,options)=>{calls.push({url,options});if(response instanceof Error)throw response;return response;}});
 // Load definitions without invoking page initialization or data loading.
 vm.runInContext(source.slice(0,source.indexOf('$("daily-date").addEventListener')),context);
 const config=JSON.parse(fs.readFileSync('frontend/data/runtime-config.json','utf8'));
 vm.runInContext(`runtime=${JSON.stringify(config)}; snapshot={games:[{sport:'nhl',id:'2026020227',start_utc:new Date(Date.now()+60000).toISOString(),home:'Home',away:'Away'}]};`,context);
 node('daily-date').value=vm.runInContext('localDay()',context);
 return {context,node,calls};
}
test('runtime config contains only public endpoint settings',()=>{
 const config=JSON.parse(fs.readFileSync('frontend/data/runtime-config.json','utf8'));
 assert.deepEqual(Object.keys(config).sort(),['simulation_endpoint','simulation_endpoint_origin']);
 assert.equal(new URL(config.simulation_endpoint).origin,config.simulation_endpoint_origin);
});
test('frontend dispatch includes credentials and reports acknowledgement',async()=>{
 const h=harness({ok:true,status:202,headers:new Headers({'Content-Type':'application/json'}),json:async()=>({accepted:true})});
 await vm.runInContext('runSimulation()',h.context);
 assert.equal(h.calls.length,1);assert.equal(h.calls[0].options.credentials,'include');assert.equal(h.calls[0].options.redirect,'error');
 assert.equal(JSON.parse(h.calls[0].options.body).scope,'all');assert.match(h.node('simulation-status').textContent,/Solicitud aceptada/);assert.equal(h.node('run-simulation').disabled,false);
});
test('authentication and CORS failures offer explicit login without retrying',async()=>{
 for(const response of [new TypeError('Failed to fetch'),{ok:false,status:401},{ok:true,status:200,headers:new Headers({'Content-Type':'text/html'})}]){
  const h=harness(response);await vm.runInContext('runSimulation()',h.context);
  assert.equal(h.calls.length,1);assert.match(h.node('simulation-status').textContent,/No se confirmó/);assert.match(h.node('simulation-status').link.href,/\/api\/nhl\/run$/);assert.equal(h.node('run-simulation').disabled,false);
 }
});
test('unsafe endpoint and selected-only requests never dispatch',async()=>{
 for(const assignment of ['runtime.simulation_endpoint+="?token=unsafe"','runtime.simulation_endpoint="http://evil.example/api/nhl/run"','document.querySelector=()=>({value:"selected"})']){
  const h=harness({});vm.runInContext(assignment,h.context);await vm.runInContext('runSimulation()',h.context);assert.equal(h.calls.length,0);
 }
});

test('missing daily feed can use the published official NHL slate without inventing scores',()=>{
 const h=harness({});
 const slate=sampleSlate();
 h.context.slate=slate;
 const snapshot=vm.runInContext('nhlScheduleSnapshot(slate)',h.context);
 assert.equal(snapshot.games.length,slate.games.length);
 assert.equal(snapshot.games[0].id,String(slate.games[0].game_id));
 assert.equal(snapshot.games[0].sport,'nhl');
 assert.equal(snapshot.games.find(g=>g.status==='OFF').completed,true);
 assert.ok(snapshot.games.every(g=>g.home_score===undefined&&g.away_score===undefined));
 assert.equal(vm.runInContext('nhlScheduleSnapshot({games:[]})',h.context),null);
 vm.runInContext('snapshot=nhlScheduleSnapshot(slate)',h.context);
 h.node('daily-date').value=slate.date;
 assert.ok(vm.runInContext('activeGames().length',h.context)>0);
});

test('page load recovers from missing daily feed and retains runner configuration',async()=>{
 const h=harness({});
 const slate=sampleSlate();
 const config=JSON.parse(fs.readFileSync('frontend/data/runtime-config.json','utf8'));
 h.context.fetch=async path=>({ok:!path.endsWith('/daily.json'),status:404,json:async()=>path.includes('nhl-complete-slate')?slate:path.includes('runtime-config')?config:[]});
 vm.runInContext('renderGames=()=>{}',h.context);
 await vm.runInContext('load()',h.context);
 assert.equal(vm.runInContext('snapshot.games.length',h.context),slate.games.length);
 assert.equal(vm.runInContext('runtime.simulation_endpoint',h.context),config.simulation_endpoint);
});

test('changing date updates calendar, summary, event and dispatch date with no stale IDs',async()=>{
 const h=harness({ok:true,status:202,headers:new Headers({'Content-Type':'application/json'}),json:async()=>({accepted:true})});
 const today=vm.runInContext('localDay()',h.context),next=new Date(today+'T12:00:00Z');next.setUTCDate(next.getUTCDate()+1);const tomorrow=next.toISOString().slice(0,10);
 h.context.calendar={kind:'nhl_calendar',included_dates:[today,tomorrow],games:[{id:'2026020232',sport:'nhl',home:'ANA',away:'OTT',start_utc:tomorrow+'T23:00:00Z',status:'FUT',completed:false}],as_of_utc:new Date().toISOString()};
 vm.runInContext('nhlCalendar=calendar',h.context);h.node('daily-date').value=tomorrow;
 vm.runInContext('changeDate()',h.context);
 assert.match(h.node('daily-label').textContent,/1 partidos/);assert.equal(h.node('run-simulation').disabled,false);assert.match(h.node('run-simulation').textContent,new RegExp(tomorrow));
 assert.equal(h.calls.find(x=>x.event)?.event.detail.date,tomorrow);
 await vm.runInContext('runSimulation()',h.context);
 const request=h.calls.find(x=>x.options);assert.deepEqual(JSON.parse(request.options.body).event_ids,['2026020232']);assert.equal(JSON.parse(request.options.body).date,tomorrow);
 h.node('daily-date').value='2099-01-01';vm.runInContext('changeDate()',h.context);assert.equal(h.node('run-simulation').disabled,true);assert.match(h.node('nhl-pending-summary').textContent,/no disponible/);
 h.node('daily-date').value='';assert.doesNotThrow(()=>vm.runInContext('changeDate()',h.context));
});
test('a known empty date differs from an unpublished date and disables execution',()=>{
 const h=harness({});const today=vm.runInContext('localDay()',h.context);
 h.context.calendar={kind:'nhl_calendar',included_dates:[today],games:[]};vm.runInContext('nhlCalendar=calendar; snapshot=null',h.context);
 h.node('daily-date').value=today;vm.runInContext('changeDate()',h.context);
 assert.equal(h.node('run-simulation').disabled,true);assert.match(h.node('daily-results').children[0].textContent,/No hay partidos programados/);
});

test('an all-pregame slate remains valid for publication',()=>{
 const h=harness({});const slate=sampleSlate();slate.games.forEach(g=>{g.game_state_at_capture='FUT';});h.context.slate=slate;
 const snapshot=vm.runInContext('nhlScheduleSnapshot(slate)',h.context);
 assert.equal(snapshot.games.length,2);assert.ok(snapshot.games.every(g=>g.completed===false));
});
