/* Focused owner-facing projection of durable control-plane state. */
import { openView, registerView } from './workspaceWindowManager.js';
import { errorState, emptyState, loadingState, moduleHeader, provenanceBadge, statusBadge } from './ui-components.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = async (path, options={}) => { const r=await fetch(path,{credentials:'same-origin',headers:options.body?{'Content-Type':'application/json'}:undefined,...options}); const d=await r.json().catch(()=>({})); if(!r.ok) throw Error(d.detail||`Request failed (${r.status})`); return d; };
let tab='Runs';

function runCard(run) { return `<button type="button" class="work-card control-run-card" data-run-id="${esc(run.id)}"><strong>${esc(run.id)}</strong><span>${statusBadge(run.status||run.lifecycle_state,'info')}</span><small>${esc(run.domain||'general')} · ${esc(run.current_step||run.lifecycle_state||'created')}</small></button>`; }
function evalCard(item, kind) { return `<article class="hades-record-card"><div><strong>${esc(item.title||item.scenario_key||item.id)}</strong><p>${esc(item.domain||item.taxonomy||kind)}</p></div><div>${statusBadge(item.status||'unknown', item.status==='admitted'||item.passed===1?'success':item.status==='pending_review'?'warning':'info')}</div></article>`; }

async function inspector(id) {
  const [run, preview, validation, replay, traces] = await Promise.all([api(`/api/work/runs/${encodeURIComponent(id)}`),api(`/api/work/runs/${encodeURIComponent(id)}/preview`),api(`/api/work/runs/${encodeURIComponent(id)}/validate`,{method:'POST',body:'{}'}),api(`/api/work/runs/${encodeURIComponent(id)}/replay`),api(`/api/work/runs/${encodeURIComponent(id)}/traces`)]);
  const actions=(preview.actions||[]).map(a=>`<article class="work-card"><strong>${esc(a.operation||a.action_id||'Unknown')}</strong><span>${esc(a.contract?.effect_class||'unknown')} · ${esc(a.contract?.risk_level||'unknown')}</span><small>${esc(a.contract?.executor_key||'unbound')} ${a.contract?.irreversible?'· IRREVERSIBLE':''}</small></article>`).join('')||'<p class="muted">No actions.</p>';
  return `<section class="control-inspector"><div class="work-header"><div><h2>Run Inspector</h2><p>${esc(id)} · ${esc(run.lifecycle_state||run.status)}</p></div>${statusBadge(validation.valid?'Validated':'Needs review',validation.valid?'success':'warning')}</div><div class="work-grid"><section><h3>Intent / Plan</h3><pre>${esc(JSON.stringify(run.intent||{},null,2))}</pre><h3>Actions</h3>${actions}</section><section><h3>Validation</h3>${validation.valid?'<p>Structurally valid.</p>':`<pre>${esc(JSON.stringify(validation.failures,null,2))}</pre>`}<h3>Knowledge gaps</h3><pre>${esc(JSON.stringify(preview.knowledge_gaps||[],null,2))}</pre></section><section><h3>Locks / Verification</h3><pre>${esc(JSON.stringify({locks:preview.locks,verification:run.verification},null,2))}</pre><h3>Replay</h3><p>${esc(replay.lifecycle_state)} · ${esc(replay.event_count)} events</p></section><section><h3>Execution trace</h3>${(traces.spans||[]).map(s=>`<article class="work-card"><strong>${esc(s.name)}</strong><small>${esc(s.status)} · ${esc(s.duration_ms)} ms</small></article>`).join('')||'<p class="muted">No trace spans.</p>'}</section></div></section>`;
}

async function load(el) {
  const body=el.querySelector('.hades-window-body'); body.innerHTML=loadingState('Loading Control Center…');
  try {
    const [runs, scenarios, failures]=await Promise.all([api('/api/work/runs'),api('/api/work/evaluations/scenarios'),api('/api/work/evaluations/failures')]);
    const runRows=runs.runs||[]; const content=tab==='Runs'?`${runRows.length?`<div class="hades-record-list">${runRows.map(runCard).join('')}</div>`:emptyState('No durable Runs','Runs, plans, approvals, and verification will appear here.')}`:tab==='Evaluations'?`${(scenarios||[]).map(x=>evalCard(x,'scenario')).join('')}${(failures||[]).map(x=>evalCard(x,'failure')).join('')||emptyState('No evaluation records','Evaluation corpus results and reviewed failures will appear here.')}`:`<p class="muted">Select a Run to inspect its preview, validation, replay, locks, and trace.</p>`;
    body.innerHTML=`${moduleHeader({icon:'developer',title:'Control Center',description:'Durable Runs, evaluations, and execution evidence.',primary:'Refresh',primaryId:'control-refresh'})}<nav class="hades-module-tabs"><button class="hades-module-tab${tab==='Runs'?' active':''}" data-control-tab="Runs">Runs</button><button class="hades-module-tab${tab==='Evaluations'?' active':''}" data-control-tab="Evaluations">Evaluations</button><button class="hades-module-tab${tab==='Inspector'?' active':''}" data-control-tab="Inspector">Inspector</button></nav><div id="control-content">${content}</div>`;
    body.querySelector('#control-refresh').onclick=()=>load(el);
    body.querySelectorAll('[data-control-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.controlTab;load(el);});
    body.querySelectorAll('[data-run-id]').forEach(b=>b.onclick=async()=>{tab='Inspector';body.querySelector('#control-content').innerHTML=loadingState('Loading Run Inspector…');try{body.querySelector('#control-content').innerHTML=await inspector(b.dataset.runId);}catch(e){body.querySelector('#control-content').innerHTML=errorState(e.message);}});
  } catch(error) { body.innerHTML=errorState(error.message,'control-retry'); body.querySelector('#control-retry')?.addEventListener('click',()=>load(el)); }
}

export function openControlCenter(){const el=openView('control-center',null,'Control Center',loadingState());load(el);return el;}
registerView('control-center',()=>openControlCenter());
export default {openControlCenter};
