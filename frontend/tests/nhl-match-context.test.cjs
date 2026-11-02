const test=require('node:test');
const assert=require('node:assert/strict');
const {select}=require('../nhl-match-context.js');
const game={game_id:'2026020232',home:'BOS',away:'VGK',start_utc:'2026-11-03T00:00:00Z'};
const snapshot={kind:'nhl_match_context_v1',as_of_utc:'2026-11-02T20:00:00Z',games:[game]};
test('requires exact fixture, sides and start; duplicate context rejected',()=>{
 assert.equal(select(snapshot,game),game);
 for(const change of [{home:'VGK'},{game_id:'2026020233'},{start_utc:'2026-11-04T00:00:00Z'}])assert.equal(select(snapshot,{...game,...change}),null);
 assert.equal(select({...snapshot,games:[game,game]},game),null);
});
test('post-start, malformed and missing snapshots cannot provide pregame context',()=>{
 for(const data of [null,{}, {...snapshot,as_of_utc:game.start_utc},{...snapshot,as_of_utc:'invalid'}])assert.equal(select(data,game),null);
});
