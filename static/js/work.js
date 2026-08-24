let pane = null;
let windowEl = null;
import { openWindow, close as closeWindow, registerView } from './workspaceWindowManager.js';
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, options={}) { const r=await fetch(path,{credentials:'same-origin',headers:options.body?{'Content-Type':'application/json'}:undefined,...options}); const d=await r.json().catch(()=>({})); if(!r.ok) throw Error(d.detail||`Request failed (${r.status})`); return d; }
function render(d) {
  const goals=(d.goals||[]).map(g=>`<article class="work-card"><strong>${esc(g.title)}</strong><span>${esc(g.status)}</span><small>${esc(g.desired_outcome||'No desired outcome')}</small></article>`).join('')||'<p class="muted">No active goals.</p>';
  const tasks=(d.tasks||[]).filter(t=>t.status!=='completed').slice(0,12).map(t=>`<article class="work-card"><strong>${esc(t.title)}</strong><span>${esc(t.status)}</span><small>${esc(t.description||'')}</small></article>`).join('')||'<p class="muted">No pending tasks.</p>';
  const runs=(d.runs||[]).filter(r=>!['completed','cancelled'].includes(r.status)).slice(0,12).map(r=>`<article class="work-card"><strong>${esc(r.id)}</strong><span>${esc(r.status)}</span><small>${esc(r.domain)} · ${esc(r.current_step||'queued')}</small></article>`).join('')||'<p class="muted">No active runs.</p>';
  pane.innerHTML=`<div class="work-header"><div><h2>Work</h2><p>Durable goals, tasks, runs, and commitments.</p></div><button id="work-close">Close</button></div><div class="work-actions"><button id="work-new-goal">New goal</button><button id="work-refresh">Refresh</button></div><div class="work-grid"><section><h3>Active goals</h3>${goals}</section><section><h3>Current tasks</h3>${tasks}</section><section><h3>Runs / resumption</h3>${runs}</section><section><h3>Open commitments</h3>${(d.commitments||[]).map(c=>`<article class="work-card"><strong>${esc(c.text)}</strong><span>${esc(c.status)}</span><small>${esc(c.due_at||'No due date')}</small></article>`).join('')||'<p class="muted">No open commitments.</p>'}</section></div>`;
  pane.querySelector('#work-close').onclick=close; pane.querySelector('#work-refresh').onclick=load; pane.querySelector('#work-new-goal').onclick=createGoal;
}
async function load(){try{render(await api('/api/work/overview'));}catch(e){if(pane)pane.innerHTML=`<p class="security-error">${esc(e.message)}</p>`;}}
async function createGoal(){const title=prompt('Goal title'); if(!title?.trim())return; const outcome=prompt('Desired outcome')||''; try{await api('/api/work/goals',{method:'POST',body:JSON.stringify({title:title.trim(),desired_outcome:outcome})});await load();}catch(e){alert(e.message);}}
function close(){closeWindow('work-overview');pane=null;windowEl=null;document.getElementById('tool-work-btn')?.classList.remove('active');}
export function togglePanel(){if(pane)close();else{windowEl=openWindow({id:'work-overview',view:'work',title:'Work',content:''});pane=windowEl.querySelector('.hades-window-body');document.getElementById('tool-work-btn')?.classList.add('active');load();}}
registerView('work', () => { if (!pane) togglePanel(); });
export default {togglePanel};
