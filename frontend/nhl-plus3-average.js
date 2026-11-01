"use strict";
// Pure calculations shared by the NHL UI and Node regression tests.
(function(root,factory){
 const api=factory();
 if(typeof module!=="undefined"&&module.exports)module.exports=api;
 if(root)root.PulsoNhlPlus3=api;
})(typeof globalThis!=="undefined"?globalThis:null,function(){
 const valid=x=>typeof x==="number"&&Number.isFinite(x)&&x>=0&&x<=1;
 function summarize(games){
  const values=[];
  for(const game of games||[]){
   if(game?.status!=="experimental_forecast")continue;
   if(valid(game.home_plus3))values.push(game.home_plus3);
   if(valid(game.away_plus3))values.push(game.away_plus3);
  }
  return {count:values.length,mean:values.length?values.reduce((a,b)=>a+b,0)/values.length:null};
 }
 function higher(value,summary){return valid(value)&&summary.count>0&&value>summary.mean;}
 return {summarize,higher};
});
