"use strict";
const assert=require("node:assert/strict");
const {summarize,higher}=require("../nhl-plus3-average.js");
const tests=[
 {status:"experimental_forecast",home_plus3:.4,away_plus3:.2},
 {status:"experimental_forecast",home_plus3:.3,away_plus3:.5},
 {status:"pregame_forecast_unavailable",home_plus3:.99,away_plus3:.99}
];
const s=summarize(tests);
assert.equal(s.count,4);assert.ok(Math.abs(s.mean-.35)<1e-12);
assert.equal(higher(.4,s),true);
assert.equal(higher(.3,s),false);
assert.equal(higher(.35,s),false);
assert.equal(higher(NaN,s),false);
assert.deepEqual(summarize([{status:"pregame_forecast_unavailable"}]),{count:0,mean:null});
console.log("NHL +3 daily-average tests passed");
