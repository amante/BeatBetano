// PULSO NHL authenticated GitHub Actions dispatcher (Cloudflare Worker).
// Deploy behind Cloudflare Access; ALSO verify the Access JWT cryptographically.
// Environment vars: ACCESS_TEAM_DOMAIN, ACCESS_AUD, ALLOWED_ORIGIN.
// Secret: GITHUB_TOKEN (fine-grained actions:write for only this repository).
const json=(body,status=200,extra={})=>new Response(JSON.stringify(body),{status,headers:{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store",...extra}});
const b64=value=>Uint8Array.from(atob(value.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(value.length/4)*4,"=")),c=>c.charCodeAt(0));
function envValid(env){
 return /^https:\/\/[a-zA-Z0-9.-]+$/.test(env.ACCESS_TEAM_DOMAIN||"")&&
 /^https:\/\/[a-zA-Z0-9.-]+$/.test(env.ALLOWED_ORIGIN||"")&&
 typeof env.ACCESS_AUD==="string"&&env.ACCESS_AUD.length>10&&
 typeof env.GITHUB_TOKEN==="string"&&env.GITHUB_TOKEN.length>10;
}
async function accessAuthorized(request,env){
 const jwt=request.headers.get("Cf-Access-Jwt-Assertion");
 if(!jwt)return false;
 const parts=jwt.split(".");if(parts.length!==3)return false;
 let header,payload;
 try{header=JSON.parse(new TextDecoder().decode(b64(parts[0])));payload=JSON.parse(new TextDecoder().decode(b64(parts[1])));}catch{return false;}
 const now=Math.floor(Date.now()/1000);
 if(header.alg!=="RS256"||!header.kid||payload.iss!==env.ACCESS_TEAM_DOMAIN||
    !Array.isArray(payload.aud)||!payload.aud.includes(env.ACCESS_AUD)||
    !Number.isFinite(payload.exp)||payload.exp<=now||
    !Number.isFinite(payload.nbf)&&payload.nbf!==undefined||payload.nbf>now)return false;
 const certs=await fetch(env.ACCESS_TEAM_DOMAIN+"/cdn-cgi/access/certs");
 if(!certs.ok)return false;
 const keys=(await certs.json()).keys||[];
 const jwk=keys.find(k=>k.kid===header.kid&&k.kty==="RSA"&&k.alg==="RS256");
 if(!jwk)return false;
 try{
  const key=await crypto.subtle.importKey("jwk",jwk,{name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["verify"]);
  return await crypto.subtle.verify("RSASSA-PKCS1-v1_5",key,b64(parts[2]),new TextEncoder().encode(parts[0]+"."+parts[1]));
 }catch{return false;}
}
export default {async fetch(request,env){
 if(!envValid(env))return json({error:"Backend not configured"},503);
 const origin=request.headers.get("Origin");
 const allowed=origin===env.ALLOWED_ORIGIN;
 const cors=allowed?{"Access-Control-Allow-Origin":origin,"Access-Control-Allow-Credentials":"true","Vary":"Origin"}:{};
 if(request.method==="OPTIONS"){
  if(!allowed)return json({error:"Origin forbidden"},403);
  return new Response(null,{status:204,headers:{...cors,"Access-Control-Allow-Methods":"POST, OPTIONS","Access-Control-Allow-Headers":"Content-Type","Access-Control-Max-Age":"600"}});
 }
 if(request.method!=="POST")return json({error:"Method not allowed"},405,cors);
 if(!allowed)return json({error:"Origin forbidden"},403);
 if(new URL(request.url).pathname!=="/api/nhl/run")return json({error:"Not found"},404,cors);
 if(!(request.headers.get("Content-Type")||"").startsWith("application/json"))return json({error:"Expected JSON"},415,cors);
 try{if(!await accessAuthorized(request,env))return json({error:"Cloudflare Access authentication required"},401,cors);}
 catch{return json({error:"Identity verification unavailable"},503,cors);}
 let input;try{input=await request.json();}catch{return json({error:"Invalid JSON"},400,cors);}
 if(input?.sport!=="nhl"||input?.scope!=="all"||
    !Array.isArray(input.event_ids)||!input.event_ids.every(id=>/^\d{8,12}$/.test(id))||
    !/^20\d{2}-\d{2}-\d{2}$/.test(input.date||""))return json({error:"Only full-slate NHL runs are supported"},400,cors);
 const day=new Date(input.date+"T00:00:00Z");
 const now=new Date(),today=Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());
 if(!Number.isFinite(day.valueOf())||day.toISOString().slice(0,10)!==input.date||
    day.valueOf()<today||day.valueOf()>today+7*86400000)return json({error:"Date must be today through seven days ahead (UTC)"},400,cors);
 const github=await fetch("https://api.github.com/repos/amante/BeatBetano/actions/workflows/pulso-nhl-prospective.yml/dispatches",{
  method:"POST",headers:{"Accept":"application/vnd.github+json","Authorization":"Bearer "+env.GITHUB_TOKEN,
   "X-GitHub-Api-Version":"2022-11-28","User-Agent":"BeatBetano-NHL-runner"},
  body:JSON.stringify({ref:"main",inputs:{day:input.date}})});
 if(github.status!==204)return json({error:"Workflow dispatch failed",status:github.status},502,cors);
 return json({accepted:true,message:"GitHub Actions workflow dispatch accepted; not yet completed",workflow_url:"https://github.com/amante/BeatBetano/actions/workflows/pulso-nhl-prospective.yml"},202,cors);
}};
