let pane = null;
let windowEl = null;
import { openWindow, close as closeWindow, registerView } from './workspaceWindowManager.js';
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, options={}) { const r=await fetch(path,{credentials:'same-origin',headers:options.body?{'Content-Type':'application/json'}:undefined,...options}); const d=await r.json().catch(()=>({})); if(!r.ok) throw Error(d.detail||`Request failed (${r.status})`); return d; }
async function openWorkEntity(kind, id, title) {
  const el = openWindow({id:`work:${kind}:${id}`, view:`work-${kind}`, title, content:'<p>Loading…</p>'});
  const body = el.querySelector('.hades-window-body');
  let row;
  if (kind === 'run') row = await api(`/api/work/runs/${encodeURIComponent(id)}`);
  else {
    const endpoint = kind === 'goal' ? 'goals' : kind === 'project' ? 'projects' : 'tasks';
    const data = await api(`/api/work/${endpoint}`);
    row = (data[endpoint] || []).find(item => item.id === id) || {id, status:'not found'};
  }
  body.innerHTML = `<div><h2>${esc(title)}</h2><p>Status: ${esc(row.status || '—')}</p><pre>${esc(JSON.stringify(row, null, 2))}</pre>${kind === 'run' && row.task_id ? `<button class="work-related-task" data-id="${esc(row.task_id)}">Open task</button>` : ''}</div>`;
  body.querySelector('.work-related-task')?.addEventListener('click', () => openWorkEntity('task', row.task_id, 'Work task'));
  return el;
}
function render(d) {
  const goals=(d.goals||[]).map(g=>`<button class="work-card work-entity-link" data-kind="goal" data-id="${esc(g.id)}"><strong>${esc(g.title)}</strong><span>${esc(g.status)}</span><small>${esc(g.desired_outcome||'No desired outcome')}</small></button>`).join('')||'<p class="muted">No active goals.</p>';
  const tasks=(d.tasks||[]).filter(t=>t.status!=='completed').slice(0,12).map(t=>`<button class="work-card work-entity-link" data-kind="task" data-id="${esc(t.id)}"><strong>${esc(t.title)}</strong><span>${esc(t.status)}</span><small>${esc(t.description||'')}</small></button>`).join('')||'<p class="muted">No pending tasks.</p>';
  const runs=(d.runs||[]).filter(r=>!['completed','cancelled'].includes(r.status)).slice(0,12).map(r=>`<button class="work-card work-entity-link" data-kind="run" data-id="${esc(r.id)}"><strong>${esc(r.id)}</strong><span>${esc(r.status)}</span><small>${esc(r.domain)} · ${esc(r.current_step||'queued')}</small></button>`).join('')||'<p class="muted">No active runs.</p>';
  const review=d.review||{};
  const reviewCards=[
    ...(review.overdue_commitments||[]).map(x=>`<article class="work-card"><strong>Overdue: ${esc(x.text)}</strong><span>commitment</span><small>${esc(x.due_at||'')}</small></article>`),
    ...(review.blocked_tasks||[]).map(x=>`<article class="work-card"><strong>Blocked: ${esc(x.title)}</strong><span>task</span><small>Needs review</small></article>`),
    ...(review.waiting_runs||[]).map(x=>`<article class="work-card"><strong>Waiting: ${esc(x.current_step||x.id)}</strong><span>${esc(x.status)}</span><small>${esc(x.domain||'work')}</small></article>`)
  ].join('') || '<p class="muted">Nothing urgent in the deterministic review.</p>';
  pane.innerHTML=`<div class="work-header"><div><h2>Work</h2><p>Durable goals, tasks, runs, and commitments.</p></div><button id="work-close">Close</button></div><div class="work-actions"><button id="work-new-goal">New goal</button><button id="work-refresh">Refresh</button></div><div class="work-grid"><section><h3>Daily review</h3>${reviewCards}</section><section><h3>Active goals</h3>${goals}</section><section><h3>Current tasks</h3>${tasks}</section><section><h3>Runs / resumption</h3>${runs}</section><section><h3>Open commitments</h3>${(d.commitments||[]).map(c=>`<article class="work-card"><strong>${esc(c.text)}</strong><span>${esc(c.status)}</span><small>${esc(c.due_at||'No due date')}</small></article>`).join('')||'<p class="muted">No open commitments.</p>'}</section></div>`;
  pane.querySelector('#work-close').onclick=close; pane.querySelector('#work-refresh').onclick=load; pane.querySelector('#work-new-goal').onclick=createGoal;
  pane.querySelectorAll('.work-entity-link').forEach(button => button.onclick = () => openWorkEntity(button.dataset.kind, button.dataset.id, `Work ${button.dataset.kind}`));
}
async function load(){try{const [overview,review]=await Promise.all([api('/api/work/overview'),api('/api/work/review')]);render({...overview,review});}catch(e){if(pane)pane.innerHTML=`<p class="security-error">${esc(e.message)}</p>`;}}
async function createGoal(){const title=prompt('Goal title'); if(!title?.trim())return; const outcome=prompt('Desired outcome')||''; try{await api('/api/work/goals',{method:'POST',body:JSON.stringify({title:title.trim(),desired_outcome:outcome})});await load();}catch(e){alert(e.message);}}
function close(){closeWindow('work-overview');pane=null;windowEl=null;document.getElementById('tool-work-btn')?.classList.remove('active');}
export function togglePanel(){if(pane)close();else{windowEl=openWindow({id:'work-overview',view:'work',title:'Work',content:''});pane=windowEl.querySelector('.hades-window-body');document.getElementById('tool-work-btn')?.classList.add('active');load();}}
registerView('work', () => { if (!pane) togglePanel(); });
export default {togglePanel};
