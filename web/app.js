/* The browser only replays exported Python experiments. No hidden client-side
 * physiology engine can diverge from the reported benchmark. See build_web.py. */
'use strict';
const $ = id => document.getElementById(id);
const descriptions = {
  nominal: 'No injected fault. The synthetic patient rewarms from 32 to 37 °C. This is an important check for needless intervention and excess pump use.',
  hemodilution: 'Hemoglobin decreases by 2.0 g/dL over minutes 5–8. Extra flow may compensate for reduced oxygen content, subject to pressure and drainage limits.',
  hb_bias: 'True hemoglobin falls by 1.8 g/dL while the inline sensor acquires a +2.0 g/dL bias. Independent simulated lab samples arrive every three minutes.',
  venous_obstruction: 'Venous drainage falls to 46% of its unobstructed value from minutes 9.6–13.4. Trying to preserve delivery with higher pump flow can drain the reservoir.',
  oxygenator_loss: 'Arterial saturation declines by 0.16. This is a scripted gas-exchange perturbation, not a model of any commercial oxygenator.',
  compound: 'Hemodilution, positive Hb bias, transient drainage restriction and saturation loss overlap. The inline Hb channel also drops out from minutes 8–11.4.',
  unmodeled_level_bias: 'A +0.40 L reservoir measurement bias accompanies poor drainage and hemodilution. Original Sentinel trusts this reading. Guarded Sentinel detects implausible level steps and applies an offset estimate plus a reserve margin; compare its reservoir and oxygen-delivery tradeoff.'
};
let timer = null;
function dataset() { return $('experiment').value==='continuity'?CONTINUITY_STUDY:$('experiment').value==='braking'?BRAKING_STUDY:$('experiment').value==='verified'?VERIFIED_STUDY:$('experiment').value==='submission'?SUBMISSION_STUDY:$('experiment').value==='reference'?REFERENCE_STUDY:$('experiment').value==='robustness'?ROBUSTNESS:$('experiment').value==='comparison'?COMPARISON:PERFUSION; }
function run() { return dataset().runs[$('scenario').value+'/'+$('policy').value]; }
const originalLabels = {
  sentinel_guarded:'Guarded Sentinel · level-step correction',
  sentinel:'Sentinel · bounded predictive', reactive:'Reactive oxygen delivery',
  fixed:'Fixed indexed flow', no_calibration:'Ablation · no Hb calibration',
  no_lookahead:'Ablation · no reservoir look-ahead'
};
function switchExperiment(){
  const comparison=$('experiment').value!=='original';
  const source=dataset();
  const options=comparison?source.variants.map(v=>{
    const label=v.label||(v.family==='reserve'?`Always reserve ${v.options.reserve_margin.toFixed(2)} L`:
      v.family==='flow_cap'?`Flow cap ${v.options.flow_cap_index.toFixed(1)} L/min/m²`:
      v.id==='guarded'?'Guarded Sentinel':'Original Sentinel');
    return [v.id,label];
  }):Object.entries(originalLabels);
  const previousScenario=$('scenario').value;
  $('scenario').innerHTML=source.protocol.scenarios.map(value=>`<option value="${value}">${source.labels?.[value]||value.replaceAll('_',' ')}</option>`).join('');
  $('scenario').value=source.protocol.scenarios.includes(previousScenario)?previousScenario:source.protocol.scenarios[0];
  $('policy').innerHTML=options.map(([value,label])=>`<option value="${value}">${label}</option>`).join('');
  $('policy').value=source.protocol.default_policy||(comparison?'guarded':'sentinel');
  $('seed-note').textContent=`Representative virtual patient · Seed ${source.protocol.start_seed} · ${(source.protocol.duration||1200)/60}-minute experiment`;
  $('timing-note').textContent=`Observations and decisions come from the start of each ${source.protocol.dt||2}-second interval; physical truth is at interval end. Display traces keep every third interval plus the last sample. Metrics use full resolution. The browser replays Python output.`;
  $('cohort-label').textContent=`${$('experiment').value==='continuity'?'FROZEN CONTINUITY COMPARISON':$('experiment').value==='braking'?'FROZEN BRAKING COMPARISON':$('experiment').value==='verified'?'FROZEN GENERAL-PI COMPARISON':$('experiment').value==='reference'?'REFERENCE TEST':$('experiment').value==='robustness'?'FROZEN-POLICY STRESS TEST':comparison?'FINAL EVALUATION':'ORIGINAL COHORT'} / ${source.protocol.n} PAIRED VIRTUAL PATIENTS`;
  $('cohort-note').textContent=comparison?
    `Difference = selected strategy − ${source.protocol.baseline_label||'Guarded Sentinel'}. Settings were selected on separate development seeds. Synthetic bootstrap intervals; no clinical benefit established.`:
    'Difference = selected strategy − reactive. Bootstrap intervals describe the synthetic sampler, not clinical benefit.';
  select();
}
function point() { const r=run(); return Math.min(+$('time').value,r.t.length-1); }
function clock(seconds) { return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(Math.round(seconds%60)).padStart(2,'0'); }
function chart(id, series, maxY, threshold, yLabel, index) {
  const r=run(), W=800, H=280, left=55, right=15, top=18, bottom=40;
  const duration=dataset().protocol.duration||1200;
  const x=t=>left+t/duration*(W-left-right), y=v=>H-bottom-v/maxY*(H-top-bottom);
  let s='';
  for(let i=0;i<=4;i++){
    const v=maxY*i/4;
    s+=`<line x1="${left}" x2="${W-right}" y1="${y(v)}" y2="${y(v)}" stroke="#2a393b"/><text x="${left-10}" y="${y(v)+4}" text-anchor="end">${v.toFixed(maxY<10?2:0)}</text>`;
  }
  for(let tick=0;tick<=4;tick++){ const m=tick*duration/240; s+=`<text x="${x(m*60)}" y="${H-12}" text-anchor="middle">${m} min</text>`; }
  s+=`<text x="${left}" y="12">${yLabel}</text><line x1="${left}" x2="${W-right}" y1="${y(threshold)}" y2="${y(threshold)}" stroke="#ffbf76" stroke-dasharray="5 5"/>`;
  for(const [key,color] of series){
    const points=r.t.map((t,i)=>`${x(t).toFixed(1)},${y(r[key][i]).toFixed(1)}`).join(' ');
    s+=`<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2.2"/>`;
    s+=`<circle cx="${x(r.t[index])}" cy="${y(r[key][index])}" r="4" fill="${color}"/>`;
  }
  s+=`<line x1="${x(r.t[index])}" x2="${x(r.t[index])}" y1="${top}" y2="${H-bottom}" stroke="#b6c5be" opacity=".5"/>`;
  $(id).innerHTML=s;
}
function render(){
  const r=run(), i=point();
  $('time').max=r.t.length-1;
  for(const key of ['do2','monitor','reservoir','pressure']) $(key).textContent=r[key][i].toFixed(key==='reservoir'?2:0);
  $('clock').textContent=clock(r.t[i]);
  chart('oxygen-chart',[['do2','#c2f296'],['monitor','#65d7d0']],Math.ceil(Math.max(...r.do2,...r.monitor,350)/100)*100,280,'mL O₂/min/m²',i);
  const levels=[['reservoir','#c2f296']];
  if(r.level_sensor) levels.push(['level_sensor','#65d7d0']);
  const hasLower=r.level_lower&&r.level_lower.every(Number.isFinite);
  if(hasLower) levels.push(['level_lower','#ffbf76']);
  const upperLevel=Math.max(...r.reservoir,...(r.level_sensor||[]),...(hasLower?r.level_lower:[]));
  chart('reservoir-chart',levels,Math.max(1.5,Math.ceil(upperLevel*2)/2),.25,'L',i);
  $('reservoir-legend').textContent=r.level_sensor?
    (hasLower?'True · sensed · control lower estimate':'True · sensed'):'Volume (L)';
  const messages=[];
  if(r.do2[i]<280) messages.push('True delivery below the experimental target');
  if(r.do2[i]<280&&r.monitor[i]>=280) messages.push('Monitor currently suggests adequate delivery');
  if(r.reservoir[i]<.25) messages.push('Reservoir below experimental floor');
  if(r.infeasible[i]) messages.push('Predictive constraints infeasible: fallback active');
  if(r.fault[i]) messages.push('Hb bias or stale inline channel flagged');
  if(r.level_fault[i]) messages.push('Level discontinuity flagged: offset correction and reserve margin latched');
  $('status').textContent=messages.length?messages.join(' · '):'No current experimental threshold violation or Hb fault flag.';
  $('status').className='status'+(messages.length?' warning':'');
}
function select(){
  pause(); $('time').value=0;
  $('scenario-description').textContent=dataset().descriptions?.[$('scenario').value]||descriptions[$('scenario').value];
  const m=run().metrics;
  $('run-metrics').innerHTML=`<div><strong>${m.deficit_auc.toFixed(0)}</strong><span>Delivery deficit AUC<br>mL O₂/m²</span></div><div><strong>${m.low_reservoir_s.toFixed(0)} s</strong><span>Below reservoir floor</span></div><div><strong>${m.false_reassurance_s.toFixed(0)} s</strong><span>False reassurance¹</span></div>`;
  const comparison=$('experiment').value!=='original';
  const c=dataset().comparisons.find(c=>c.scenario===$('scenario').value&&(comparison?c.variant:c.policy)===$('policy').value&&c.metric==='deficit_auc');
  const reference=dataset().protocol.baseline_label||(comparison?'Guarded Sentinel':'Reactive');
  $('cohort').textContent=c?`Delivery deficit AUC difference: ${c.mean.toFixed(1)} mL O₂/m² (95% paired bootstrap interval ${c.low.toFixed(1)} to ${c.high.toFixed(1)}). Negative values favor the selected strategy for this metric.`:`${reference} is the reference strategy. Select another strategy to inspect its paired difference in delivery deficit AUC.`;
  render();
}
function pause(){ clearInterval(timer);timer=null;$('play').textContent='▶ Play'; }
$('play').addEventListener('click',()=>{
  if(timer){pause();return;}
  if(point()===run().t.length-1) $('time').value=0;
  $('play').textContent='Ⅱ Pause';
  timer=setInterval(()=>{ $('time').value=point()+1;render();if(point()>=run().t.length-1)pause(); },100);
});
$('reset').addEventListener('click',()=>{pause();$('time').value=0;render();});
$('time').addEventListener('input',()=>{pause();render();});
$('scenario').addEventListener('change',select);$('policy').addEventListener('change',select);
$('experiment').addEventListener('change',switchExperiment);
function calculate(){
  const hb=+$('hb').value, flow=+$('flow').value;
  $('hb-value').textContent=hb.toFixed(1)+' g/dL';$('flow-value').textContent=flow.toFixed(1)+' L/min';
  $('calc-do2').textContent=(10*flow*(1.34*hb*.98+.0031*150)/1.85).toFixed(0);
}
$('hb').addEventListener('input',calculate);$('flow').addEventListener('input',calculate);
switchExperiment();calculate();

