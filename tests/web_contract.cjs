/* Dependency-free DOM-contract check. This executes real exported replay and
 * app code against a tiny mock DOM; it is not browser or visual-layout testing. */
'use strict';
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'web/index.html'),'utf8');
const elements={};
for(const match of html.matchAll(/id="([^"]+)"/g)){
  assert(!elements[match[1]],'Duplicate ID: '+match[1]);
  elements[match[1]]={value:'0',max:200,innerHTML:'',textContent:'',className:'',handlers:{},
    addEventListener(event,handler){this.handlers[event]=handler;}};
}
elements.scenario.value='compound';elements.policy.value='sentinel';
elements.experiment.value='original';
elements.hb.value='9';elements.flow.value='4.5';
let tick;
const context=vm.createContext({document:{getElementById(id){assert(elements[id],'Missing element '+id);return elements[id];}},
  setInterval(fn){tick=fn;return 1;},clearInterval(){tick=null;},console});
for(const match of html.matchAll(/<script src="((?:data|comparison|robustness|reference|submission|verified|braking|continuity|selective|integrity|slowdown|model-bank|reachability)[^"/]*\.js)"/g))
  vm.runInContext(fs.readFileSync(path.join(root,'web',match[1]),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(root,'web/app.js'),'utf8'),context);
const data=vm.runInContext('PERFUSION',context);
const comparison=vm.runInContext('COMPARISON',context);
const robustness=vm.runInContext('ROBUSTNESS',context);
const reference=vm.runInContext('REFERENCE_STUDY',context);
const submission=vm.runInContext('SUBMISSION_STUDY',context);
const verified=vm.runInContext('VERIFIED_STUDY',context);
assert.equal(Object.keys(data.runs).length,42);
assert.equal(Object.keys(comparison.runs).length,28);
assert.equal(Object.keys(robustness.runs).length,24);
assert.equal(Object.keys(reference.runs).length,30);
assert.equal(Object.keys(submission.runs).length,12);
assert.equal(Object.keys(verified.runs).length,12);
const braking=vm.runInContext('BRAKING_STUDY',context);assert.equal(Object.keys(braking.runs).length,18);
const continuity=vm.runInContext('CONTINUITY_STUDY',context);assert.equal(Object.keys(continuity.runs).length,18);
const selective=vm.runInContext('SELECTIVE_STUDY',context);assert.equal(Object.keys(selective.runs).length,30);
const integrity=vm.runInContext('INTEGRITY_STUDY',context);assert.equal(Object.keys(integrity.runs).length,24);
const slowdown=vm.runInContext('SLOWDOWN_STUDY',context);assert.equal(Object.keys(slowdown.runs).length,48);
const model_bank=vm.runInContext('MODEL_BANK_STUDY',context);assert.equal(Object.keys(model_bank.runs).length,40);
const reachability=vm.runInContext('REACHABILITY_STUDY',context);assert.equal(Object.keys(reachability.runs).length,21);
assert(html.includes('value="sentinel_guarded"'));
assert(html.includes('id="controller-comparison"'));
assert(!html.includes('PAPER_DRAFT.md'));
assert(!html.includes('id="manuscript"'));
for(const [experiment,source] of [['original',data],['comparison',comparison],['robustness',robustness],['reference',reference],['submission',submission],['verified',verified],['braking',braking],['continuity',continuity],['selective',selective],['integrity',integrity],['slowdown',slowdown],['model_bank',model_bank],['reachability',reachability]]){
elements.experiment.value=experiment;elements.experiment.handlers.change();
assert(elements['seed-note'].textContent.includes(String(source.protocol.start_seed)));
if(experiment==='reachability'){assert(elements['cohort-note'].textContent.includes('reuse the same 32 patients'));assert(elements['cohort-label'].textContent.includes('DEVELOPMENT ONLY'));}
if(['verified','braking','continuity','selective','integrity','slowdown','model_bank','reachability'].includes(experiment)){assert(elements['seed-note'].textContent.includes('10-minute'));assert(elements['timing-note'].textContent.includes('1-second'));}
for(const [name,run] of Object.entries(source.runs)){
  const [scenario,policy]=name.split('/');
  elements.scenario.value=scenario;elements.policy.value=policy;
  elements.scenario.handlers.change();
  assert.equal(run.level_fault.length,run.t.length);
  assert(elements['scenario-description'].textContent.length>20);
  if(experiment==='reachability'){const expected=source.protocol.scenario_seeds[scenario];assert(elements['seed-note'].textContent.includes('Seed '+expected));if(scenario.startsWith('worst_primary'))assert(elements['scenario-description'].textContent.includes('WORST-CASE'));}
  for(const i of [0,Math.floor(run.t.length/2),run.t.length-1]){
    elements.time.value=String(i);elements.time.handlers.input();
    for(const id of ['oxygen-chart','reservoir-chart']){
      assert(!/NaN|undefined|Infinity/.test(elements[id].innerHTML),id+' invalid geometry');
      assert(elements[id].innerHTML.includes('polyline'));
    }
    assert(Number.isFinite(+elements.do2.textContent));
    assert(elements.status.textContent.length>0);
  }
}
}
// Switching cohorts must reset an incompatible policy and stop playback.
elements.play.handlers.click();assert(tick);
elements.experiment.value='original';elements.experiment.handlers.change();
assert.equal(tick,null);assert.equal(elements.policy.value,'sentinel');
assert(data.protocol.scenarios.includes(elements.scenario.value));
assert.equal(+elements.time.value,0);
elements.play.handlers.click();assert(tick);tick();
elements.play.handlers.click();assert.equal(tick,null);
elements.reset.handlers.click();assert.equal(+elements.time.value,0);
elements.hb.value='10';elements.flow.value='5';elements.hb.handlers.input();
assert.equal(+elements['calc-do2'].textContent,Math.round(10*5*(1.34*10*.98+.0031*150)/1.85));
console.log('PASS: 347 scenario/policy views, cohort/scenario switching, timeline, chart coordinates, play/pause/reset, calculator and DOM IDs.');

