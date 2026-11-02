const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('frontend/daily.js','utf8');
function harness(response){
 const nodes=new Map();const node=id=>{if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',append(x){this.link=x;},addEventListener(){}});return nodes.get(id);};
 const calls=[];const context=vm.createContext({URL,URLSearchParams,Intl,Date,Set,Map,location:{search:'?sport=nhl',href:'https://amante.github.io/BeatBetano/dashboard.html',origin:'https://amante.github.io'},document:{getElementById:node,querySelector:()=>({value:'all'}),querySelectorAll:()=>[],createElement:()=>({})},fetch:async(url,options)=>{calls.push({url,options});if(response instanceof Error)throw response;return response;}});
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
