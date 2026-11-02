// Public fixtures only; run with Node 22. No credentials or model probabilities.
import {writeFile, mkdir} from 'node:fs/promises';
import {dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
export const chileDay=value=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Santiago',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
export function shiftDay(day,delta){const date=new Date(day+'T12:00:00Z');date.setUTCDate(date.getUTCDate()+delta);return date.toISOString().slice(0,10);}
export function normalizeSchedule(weeks,now=new Date()){
 const today=chileDay(now),first=shiftDay(today,-1),last=shiftDay(today,7),coverage=new Set(),games=new Map();
 for(const week of weeks){
  if(!Array.isArray(week?.gameWeek))throw Error('Invalid official NHL schedule');
  for(const day of week.gameWeek){
   if(!/^20\d{2}-\d{2}-\d{2}$/.test(day.date)||!Array.isArray(day.games))throw Error('Invalid schedule day');
   coverage.add(day.date);
   for(const g of day.games){
    if(!/^\d{10}$/.test(String(g.id))||!g.homeTeam?.abbrev||!g.awayTeam?.abbrev||!Number.isFinite(Date.parse(g.startTimeUTC)))throw Error('Invalid official NHL fixture');
    const local=chileDay(g.startTimeUTC);if(local<first||local>last)continue;
    const completed=['OFF','FINAL'].includes(g.gameState);
    games.set(String(g.id),{id:String(g.id),sport:'nhl',home:g.homeTeam.abbrev,away:g.awayTeam.abbrev,start_utc:g.startTimeUTC,status:g.gameState,completed,venue:g.venue?.default||null,home_name:g.homeTeam.commonName?.default||null,away_name:g.awayTeam.commonName?.default||null,
     home_score:completed&&Number.isFinite(g.homeTeam.score)?g.homeTeam.score:null,away_score:completed&&Number.isFinite(g.awayTeam.score)?g.awayTeam.score:null,source:'NHL official schedule'});
   }
  }
 }
 const dates=[];for(let day=first;day<=last;day=shiftDay(day,1)){if(coverage.has(day)&&coverage.has(shiftDay(day,1)))dates.push(day);}
 if(!dates.includes(today)||!dates.includes(last))throw Error('Official schedule coverage is incomplete');
 return {kind:'nhl_calendar',timezone:'America/Santiago',as_of_utc:new Date(now).toISOString(),included_dates:dates,games:[...games.values()].sort((a,b)=>a.start_utc.localeCompare(b.start_utc)),errors:[],source:'Calendario oficial NHL'};
}
export async function collectSchedule({now=new Date(),get=async url=>{const response=await fetch(url,{signal:AbortSignal.timeout(20000)});if(!response.ok)throw Error('Official schedule HTTP '+response.status);return response.json();}}={}){
 const today=chileDay(now),urls=[shiftDay(today,-1),shiftDay(today,6)].map(day=>'https://api-web.nhle.com/v1/schedule/'+day);
 return {...normalizeSchedule(await Promise.all(urls.map(get)),now),source_urls:urls};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const output=process.argv[2]||'frontend/data/nhl-schedule.json';
 const result=await collectSchedule();await mkdir(dirname(output),{recursive:true});await writeFile(output,JSON.stringify(result,null,2)+'\n');
 process.stdout.write(JSON.stringify({dates:result.included_dates.length,games:result.games.length})+'\n');
}
