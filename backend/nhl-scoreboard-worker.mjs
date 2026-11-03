// Public, read-only, on-demand NHL scoreboard. No credentials or scheduled tasks.
export default {async fetch(request,env){
 const origin=env.ALLOWED_ORIGIN;
 const headers={"Access-Control-Allow-Origin":origin,"Vary":"Origin","Cache-Control":"no-store","Content-Type":"application/json"};
 if(request.method!=="GET")return new Response(null,{status:405,headers});
 const id=new URL(request.url).searchParams.get("game");
 if(!/^\d{10}$/.test(id||""))return new Response('{"error":"Invalid game"}',{status:400,headers});
 try{const response=await fetch("https://api-web.nhle.com/v1/gamecenter/"+id+"/landing");if(!response.ok)throw Error();return new Response(JSON.stringify(await response.json()),{headers});}
 catch{return new Response('{"error":"Source unavailable"}',{status:502,headers});}
}};
