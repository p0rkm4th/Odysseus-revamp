import { openView, close as closeWindow, registerView } from './workspaceWindowManager.js';

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const api = async (path, options={}) => { const r=await fetch(path,{credentials:'same-origin',headers:options.body?{'Content-Type':'application/json'}:undefined,...options}); const d=await r.json().catch(()=>({})); if(!r.ok) throw Error(d.detail||`Request failed (${r.status})`); return d; };

function card(title, value, detail='') { return `<article class="work-card"><strong>${esc(title)}</strong><span>${esc(value)}</span><small>${esc(detail)}</small></article>`; }

export async function openHades() {
  const el=openView('hades-self', null, 'Hades', '<p>Loading Hades status…</p>');
  const body=el.querySelector('.hades-window-body');
  try {
    const [status, episodes, notifications, monitors] = await Promise.all([
      api('/api/hades/status'), api('/api/hades/episodes'), api('/api/hades/notifications?unread=true'), api('/api/hades/monitors')
    ]);
    const identity=status.identity||{}, runtime=status.runtime||{}, work=status.work||{};
    body.innerHTML=`<div class="hades-status-panel"><div class="work-header"><div><h2>Hades</h2><p>Grounded persistent-agent status</p></div><button id="hades-refresh">Refresh</button></div>
      <section><h3>Identity / runtime</h3>${card(identity.canonical_name||'Hades','installation '+(identity.installation_id||'—'),`model ${runtime.model_profile||'—'} · runtime ${runtime.runtime_version||'—'}`)}</section>
      <section><h3>Current work</h3>${card('Active goals',(work.goals||[]).length,`${(work.runs||[]).length} active runs · ${work.pending_approval?'approval pending':'no approval pending'}`)}${card('Commitments',(status.commitments||[]).length,`${status.notifications?.unread||0} unread notifications`)}</section>
      <section><h3>Capabilities</h3>${(status.capabilities||[]).slice(0,12).map(x=>card(x.capability,x.status,x.missing_executables?.join(', ')||x.execution_profile||'')).join('')}</section>
      <section><h3>Recent Episodes</h3>${(episodes.episodes||[]).slice(0,8).map(x=>card(x.title,x.outcome,`${x.episode_type} · evidence ${(x.evidence_references||[]).length}`)).join('')||'<p class="muted">No meaningful episodes recorded.</p>'}</section>
      <section><h3>Unread Notifications</h3>${(notifications.notifications||[]).map(x=>`<button class="work-card hades-notification" data-id="${esc(x.id)}"><strong>${esc(x.title)}</strong><span>${esc(x.severity)}</span><small>${esc(x.body)}</small></button>`).join('')||'<p class="muted">No unread notifications.</p>'}</section>
      <section><h3>Monitors</h3>${(monitors.monitors||[]).map(x=>card(x.name,x.enabled?'enabled':'disabled',`${x.condition_type} · tier ${x.consequence_tier}`)).join('')||'<p class="muted">No monitors configured.</p>'}</section></div>`;
    body.querySelector('#hades-refresh').onclick=()=>openHades();
    body.querySelectorAll('.hades-notification').forEach(b=>b.onclick=async()=>{await api(`/api/hades/notifications/${encodeURIComponent(b.dataset.id)}/read`,{method:'POST'});openHades();});
  } catch (e) { body.innerHTML=`<p class="security-error">${esc(e.message)}</p>`; }
  return el;
}

function close(){ closeWindow('hades-self'); }
registerView('hades-self', () => openHades());
export default {openHades, close};
