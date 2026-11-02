import {test} from 'node:test';
import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import worker from '../nhl-dispatch-worker.mjs';
globalThis.crypto ??= webcrypto;
const env={ACCESS_TEAM_DOMAIN:'https://test.cloudflareaccess.com',ACCESS_AUD:'test-audience-value',ALLOWED_ORIGIN:'https://amante.github.io',GITHUB_TOKEN:'test-only-not-a-secret'};
const endpoint='https://runner.example/api/nhl/run';
const pair=await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
const jwk={...await crypto.subtle.exportKey('jwk',pair.publicKey),kid:'test',alg:'RS256'};
const encode=x=>Buffer.from(JSON.stringify(x)).toString('base64url');
async function token(overrides={}){
 const data=encode({alg:'RS256',kid:'test'})+'.'+encode({iss:env.ACCESS_TEAM_DOMAIN,aud:[env.ACCESS_AUD],exp:Math.floor(Date.now()/1000)+300,...overrides});
 return data+'.'+Buffer.from(await crypto.subtle.sign('RSASSA-PKCS1-v1_5',pair.privateKey,new TextEncoder().encode(data))).toString('base64url');
}
const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Santiago',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const input=()=>({sport:'nhl',scope:'all',date:today(),event_ids:['2026020227']});
function request(body=input(),jwt,origin=env.ALLOWED_ORIGIN){return new Request(endpoint,{method:'POST',headers:{Origin:origin,'Content-Type':'application/json',...(jwt?{'Cf-Access-Jwt-Assertion':jwt}:{})},body:JSON.stringify(body)});}
test('preflight permits only configured origin, POST and Content-Type',async()=>{
 for(const [origin,method,header,status] of [[env.ALLOWED_ORIGIN,'POST','content-type',204],['https://evil.example','POST','content-type',403],[env.ALLOWED_ORIGIN,'DELETE','content-type',403],[env.ALLOWED_ORIGIN,'POST','authorization',403]]){
  const r=await worker.fetch(new Request(endpoint,{method:'OPTIONS',headers:{Origin:origin,'Access-Control-Request-Method':method,'Access-Control-Request-Headers':header}}),env);
  assert.equal(r.status,status);if(status===204){assert.equal(r.headers.get('Access-Control-Allow-Credentials'),'true');assert.equal(r.headers.get('Access-Control-Allow-Origin'),origin);}
 }
});
test('missing authentication, disallowed origins and configuration fail closed',async()=>{
 assert.equal((await worker.fetch(request(),env)).status,401);
 assert.equal((await worker.fetch(request(input(),null,'https://evil.example'),env)).status,403);
 const r=await worker.fetch(request(),{});assert.equal(r.status,503);assert.ok(!(await r.text()).includes(env.GITHUB_TOKEN));
 const r2=await worker.fetch(request(),{...env,GITHUB_TOKEN:''});assert.equal(r2.headers.get('Access-Control-Allow-Origin'),env.ALLOWED_ORIGIN);
});
test('signed JWT, dates, dispatch payload, and upstream failures',async()=>{
 const original=globalThis.fetch;let calls=[];let upstream=204;
 globalThis.fetch=async(url,options)=>{if(String(url).endsWith('/certs'))return Response.json({keys:[jwk]});calls.push({url,options});return new Response(null,{status:upstream});};
 try{
  for(const claims of [{aud:['wrong']},{iss:'https://wrong.example'},{exp:0},{nbf:Math.floor(Date.now()/1000)+600}])assert.equal((await worker.fetch(request(input(),await token(claims)),env)).status,401);
  const valid=await token();const parts=valid.split('.');parts[2]=(parts[2][0]==='A'?'B':'A')+parts[2].slice(1);
  assert.equal((await worker.fetch(request(input(),parts.join('.')),env)).status,401);
  for(const body of [{...input(),scope:'selected'},{...input(),date:'2026-02-30'},{...input(),date:'2000-01-01'},{...input(),date:'2099-01-01'},{...input(),event_ids:[]},{...input(),event_ids:[2026020227]}])assert.equal((await worker.fetch(request(body,valid),env)).status,400);
  assert.equal(calls.length,0);
  assert.equal((await worker.fetch(request(input(),valid),env)).status,202);
  assert.deepEqual(JSON.parse(calls[0].options.body),{ref:'main',inputs:{day:today()}});
  assert.match(calls[0].url,/pulso-nhl-prospective.yml\/dispatches$/);
  upstream=403;const failed=await worker.fetch(request(input(),valid),env);assert.equal(failed.status,502);assert.ok(!(await failed.text()).includes(env.GITHUB_TOKEN));
  globalThis.fetch=async()=>{throw Error('network');};assert.equal((await worker.fetch(request(input(),valid),env)).status,503);
 }finally{globalThis.fetch=original;}
});
test('Santiago date remains valid after UTC midnight and across DST',async()=>{
 const NativeDate=Date,original=globalThis.fetch;
 try{
  for(const instant of ['2026-11-02T01:00:00Z','2026-04-05T02:30:00Z','2026-09-06T04:30:00Z']){
   globalThis.Date=class extends NativeDate{constructor(...args){super(...(args.length?args:[instant]));}static now(){return new NativeDate(instant).valueOf();}};
   globalThis.fetch=async url=>String(url).endsWith('/certs')?Response.json({keys:[jwk]}):new Response(null,{status:204});
   const jwt=await token();assert.equal((await worker.fetch(request(input(),jwt),env)).status,202);
   const last=new Date(today()+'T12:00:00Z');last.setUTCDate(last.getUTCDate()+7);
   assert.equal((await worker.fetch(request({...input(),date:last.toISOString().slice(0,10)},jwt),env)).status,202);
   last.setUTCDate(last.getUTCDate()+1);assert.equal((await worker.fetch(request({...input(),date:last.toISOString().slice(0,10)},jwt),env)).status,400);
  }
 }finally{globalThis.Date=NativeDate;globalThis.fetch=original;}
});
