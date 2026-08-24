const esc = (v) => String(v ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
import { openView, setOwner, registerView } from './workspaceWindowManager.js';
fetch('/api/intelligence/profiles', {credentials:'same-origin'}).then(r=>r.json()).then(d=>setOwner(d.owner)).catch(()=>{});
function panel(id, title, html) {
  return openView(id, null, title, `<div><h2>${title}</h2>${html}</div>`);
}
export async function openHousehold(){
  const el=panel('household-panel','Household','<p>Loading Household…</p>');
  const r=await fetch('/api/inventory/items?domain=household&include_archived=false'); const d=await r.json();
  el.querySelector('.hades-window-body').innerHTML=`<div><h2>Household</h2><p>Kitchen & Pantry · Stock · Recipes · Locations · Intake</p><div>${(d.items||[]).map(x=>`<div class="list-item"><span>${esc(x.name)}</span><small>${esc(x.category||'item')}</small></div>`).join('')||'<p>No household items yet.</p>'}</div>`;
  return el;
}
export async function openItAssets(){
  const el=panel('it-assets-panel','IT Assets','<p>Loading IT Assets…</p>');
  const [items,net]=await Promise.all([fetch('/api/inventory/items?domain=it&include_archived=false').then(r=>r.json()),fetch('/api/network/map').then(r=>r.json())]);
  el.querySelector('.hades-window-body').innerHTML=`<div><h2>IT Assets</h2><p>Computers · Components · Network Devices · Discovered / Unidentified</p><h3>Inventory</h3>${(items.items||[]).map(x=>`<div class="list-item">${esc(x.name)} <small>${esc(x.model||x.category||'asset')}</small></div>`).join('')||'<p>No user-facing IT assets yet.</p>'}<h3>CMDB-backed devices</h3><p>${(net.nodes||[]).length} canonical nodes · ${esc(net.identity_rule||'')}</p></div>`;
  return el;
}
export async function openNetwork(){
  const el=panel('network-panel','Network','<p>Loading Network Map…</p>');
  const d=await fetch('/api/network/map').then(r=>r.json());
  el.querySelector('.hades-window-body').innerHTML=`<div><h2>Network</h2><p>Logical topology · Devices · Subnets · Services · Discovery</p><p class="muted">${esc(d.source||'CMDB')} · ${esc(d.identity_rule||'')}</p><div>${(d.nodes||[]).map(x=>`<div class="list-item"><span>${esc(x.name||x.hostname||x.id)}</span><small>${esc(x.resolution_state||'unidentified')}</small></div>`).join('')||'<p>No CMDB nodes observed.</p>'}</div></div>`;
  return el;
}
export async function openDeveloper(){
  const el=panel('developer-panel','Developer','<p>Loading Developer Mode…</p>');
  const d=await fetch('/api/developer/yolo/status').then(r=>r.json());
  const lease=d.lease; const content=`<p><b>Workspace YOLO</b></p><p>Scope: <code>${esc(d.workspace)}</code><br>Root: NO · Docker: NO<br>Authority: arbitrary workspace Bash</p><p>${lease?`Active until ${esc(lease.expires_at)} <button id="revoke-yolo">Revoke</button>`:'Inactive — requires explicit owner activation.'}</p>${lease?'': '<button id="grant-yolo">Enable for 30 minutes</button>'}`;
  el.querySelector('.hades-window-body').innerHTML=`<div><h2>Developer Mode</h2>${content}</div>`;
  if (lease) el.querySelector('#revoke-yolo').onclick=async()=>{await fetch('/api/developer/yolo/revoke',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({lease_id:lease.id})});openDeveloper();};
  else el.querySelector('#grant-yolo').onclick=async()=>{await fetch('/api/developer/yolo/grant',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({duration_seconds:1800})});openDeveloper();};
  return el;
}
registerView('household-panel', () => openHousehold());
registerView('it-assets-panel', () => openItAssets());
registerView('network-panel', () => openNetwork());
registerView('developer-panel', () => openDeveloper());
