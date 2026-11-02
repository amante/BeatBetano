import {test} from 'node:test';
import assert from 'node:assert/strict';
import {normalizeSchedule,collectSchedule,shiftDay,chileDay} from '../collect-nhl-schedule.mjs';
const now=new Date('2026-11-02T00:10:00Z');
const fixture=(id,start,gameState='FUT')=>({id,startTimeUTC:start,gameState,homeTeam:{abbrev:'ANA',score:3},awayTeam:{abbrev:'OTT',score:2}});
function weeks(){
 const dates=Array.from({length:14},(_,i)=>({date:shiftDay('2026-10-31',i),games:[]}));
 dates[1].games=[fixture(2026020231,'2026-11-02T01:00:00Z')];
 dates[2].games=[fixture(2026020232,'2026-11-03T00:00:00Z'),fixture(2026020233,'2026-11-02T20:00:00Z','OFF')];
 return [{gameWeek:dates.slice(0,7)},{gameWeek:dates.slice(7)}];
}
test('calendar covers yesterday through +7, using Santiago around UTC midnight',()=>{
 assert.equal(chileDay(now),'2026-11-01');
 const calendar=normalizeSchedule(weeks(),now);
 assert.equal(calendar.included_dates.length,9);assert.equal(calendar.included_dates[0],'2026-10-31');assert.equal(calendar.included_dates.at(-1),'2026-11-08');
 assert.equal(calendar.games.filter(g=>chileDay(g.start_utc)==='2026-11-02').length,2);
 assert.equal(calendar.games.find(g=>g.completed).home_score,3);assert.equal(calendar.games.find(g=>!g.completed).home_score,null);
 assert.equal(calendar.games[0].id,'2026020231');
});
test('explicit empty days stay known; malformed and incomplete schedules fail closed',()=>{
 const calendar=normalizeSchedule(weeks(),now);
 assert.ok(calendar.included_dates.includes('2026-11-04'));assert.ok(!calendar.games.some(g=>chileDay(g.start_utc)==='2026-11-04'));
 assert.throws(()=>normalizeSchedule([{gameWeek:[]}],now),/incomplete/);
 assert.throws(()=>normalizeSchedule([{}],now),/Invalid/);
 const broken=weeks();broken[0].gameWeek[1].games[0].startTimeUTC='invalid';assert.throws(()=>normalizeSchedule(broken,now),/fixture/);
});
test('collector requests two fixed official schedule URLs and propagates failures',async()=>{
 const urls=[];const data=weeks();
 const calendar=await collectSchedule({now,get:async url=>{urls.push(url);return data[urls.length-1];}});
 assert.deepEqual(urls,['https://api-web.nhle.com/v1/schedule/2026-10-31','https://api-web.nhle.com/v1/schedule/2026-11-07']);
 assert.equal(calendar.games.length,3);
 await assert.rejects(collectSchedule({now,get:async()=>{throw Error('offline');}}),/offline/);
});
