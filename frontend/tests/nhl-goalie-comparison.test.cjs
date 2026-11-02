const test=require('node:test');const assert=require('node:assert/strict');
const {select,reasons}=require('../nhl-goalie-comparison.js');
const game={game_id:'2026020232',home:'BOS',away:'VGK',start_utc:'2026-11-03T00:00:00Z',ml:{home:.55,away:.45}};
const slate={run_id:'123',date:'2026-11-02'};
const row={...game,baseline_p_home:.55,candidate_p_home:.6,candidate_p_away:.4,recalibration_p_home:.56,delta_vs_baseline_pp:5,delta_vs_recalibration_pp:4,status:'experimental_goalie_ml_executed',model_sha256:'model',evidence_sha256:'evidence',baseline_forecast_sha256:'forecast',feature_as_of_utc:'2026-11-02T20:00:00Z',baseline_as_of_utc:'2026-11-02T20:01:00Z',computed_at_utc:'2026-11-02T20:02:00Z'};
const packet={kind:'nhl_goalie_ml_comparison_v1',market:'ml',official:false,published_baseline_replaced:false,run_id:'123',date:'2026-11-02',games:[row]};
test('same-emission comparison preserves complementary ML and deltas',()=>{assert.equal(select(packet,slate,game),row);});
test('stale run, duplicate fixture and baseline mismatches are rejected',()=>{
 assert.equal(select(packet,{...slate,run_id:'122'},game),null);
 assert.equal(select({...packet,games:[row,row]},slate,game),null);
 assert.equal(select(packet,slate,{...game,ml:{home:.56,away:.44}}),null);
});
test('non-executed has null values, never a fake zero delta',()=>{
 const missing={...row,status:'goalie_model_not_executed',candidate_p_home:null,candidate_p_away:null,recalibration_p_home:null,delta_vs_baseline_pp:null,delta_vs_recalibration_pp:null,reasons:['missing_fitted_model']};
 assert.equal(select({...packet,games:[missing]},slate,game),missing);
 assert.equal(select({...packet,games:[{...missing,delta_vs_baseline_pp:0}]},slate,game),null);
 assert.match(reasons(missing)[0],/Falta un modelo/);
});
test('invalid probabilities, hidden recalibration and post-start computation rejected',()=>{
 for(const change of [{candidate_p_home:NaN},{candidate_p_away:.5},{delta_vs_recalibration_pp:0},{computed_at_utc:game.start_utc},{feature_as_of_utc:'2026-11-02T22:00:00Z'}])assert.equal(select({...packet,games:[{...row,...change}]},slate,game),null);
 assert.match(reasons(null)[0],/No hay una comparación/);
});
async function renderPacket(data){
 const vm=require('node:vm'),fs=require('node:fs');
 const document={createElement(tag){return {tag,children:[],append(...children){this.children.push(...children);}};}};
 const window={};
 vm.runInNewContext(fs.readFileSync(require.resolve('../nhl-goalie-comparison.js'),'utf8'),{window,document,fetch:async()=>({ok:true,json:async()=>data})});
 await window.PulsoNhlGoalieComparison.ready;
 const root=window.PulsoNhlGoalieComparison.create(slate,game);
 const text=node=>[node.textContent||'',...node.children.map(text)].join(' ');
 return text(root);
}
test('rendered experimental comparison identifies base, candidate and signed differences',async()=>{
 const text=await renderPacket(packet);
 assert.match(text,/Candidato experimental/);assert.match(text,/Con arquero/);assert.match(text,/60,0%/);assert.match(text,/\+5,00 pp/);assert.match(text,/\+4,00 pp/);
});
test('rendered absent model shows reason without candidate percentage or zero delta',async()=>{
 const missing={...row,status:'goalie_model_not_executed',candidate_p_home:null,candidate_p_away:null,recalibration_p_home:null,delta_vs_baseline_pp:null,delta_vs_recalibration_pp:null,reasons:['missing_fitted_model']};
 const text=await renderPacket({...packet,games:[missing]});
 assert.match(text,/Modelo con arquero no ejecutado/);assert.match(text,/Falta un modelo/);assert.doesNotMatch(text,/0,00 pp|Con arquero/);
});
