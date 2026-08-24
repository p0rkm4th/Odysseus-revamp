const esc = (v) => String(v ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
import { openView, setOwner, registerView } from './workspaceWindowManager.js';
fetch('/api/intelligence/profiles', {credentials:'same-origin'}).then(r=>r.json()).then(d=>setOwner(d.owner)).catch(()=>{});
function panel(id, title, html) {
  return openView(id, null, title, `<div><h2>${title}</h2>${html}</div>`);
}
function entityWindow(view, id, title, html='<p>Loading…</p>') {
  const el = openView(view, id, title, `<div><h2>${esc(title)}</h2>${html}</div>`);
  return el;
}
function bindEntityLinks(el, selector, opener) {
  el.querySelectorAll(selector).forEach(button => {
    button.addEventListener('click', () => opener(button.dataset.id));
  });
}
async function openHouseholdItem(id) {
  const el = entityWindow('household-item', id, 'Household item');
  const d = await fetch(`/api/inventory/items/${encodeURIComponent(id)}`).then(r => r.json());
  const item = d.item || {};
  el.querySelector('.hades-window-body').innerHTML = `<div><h2>${esc(item.name || 'Household item')}</h2><p>${esc(item.category || 'household')} · ${esc(item.location_name || 'No location')}</p><p>${esc(item.description || 'No description')}</p><h3>Stock</h3><pre>${esc(JSON.stringify(d.lots || [], null, 2))}</pre></div>`;
  return el;
}
async function openItAsset(id) {
  const el = entityWindow('it-asset', id, 'IT asset');
  const d = await fetch(`/api/inventory/items/${encodeURIComponent(id)}`).then(r => r.json());
  const item = d.item || {}, asset = d.asset || {};
  el.querySelector('.hades-window-body').innerHTML = `<div><h2>${esc(item.name || asset.hostname || 'IT asset')}</h2><p>${esc(item.manufacturer || '')} ${esc(item.model || '')} · ${esc(asset.status || item.category || 'asset')}</p><dl><dt>Serial</dt><dd>${esc(asset.serial_number || '—')}</dd><dt>Asset tag</dt><dd>${esc(asset.asset_tag || '—')}</dd><dt>Hostname</dt><dd>${esc(asset.hostname || '—')}</dd><dt>IPs</dt><dd>${esc((asset.ip_addresses || []).join(', ') || '—')}</dd></dl><h3>Specifications</h3><pre>${esc(JSON.stringify(asset.specs || item.metadata || {}, null, 2))}</pre><h3>Components</h3><pre>${esc(JSON.stringify(d.components || [], null, 2))}</pre></div>`;
  return el;
}
function openCmdbAsset(node) {
  const el = entityWindow('cmdb-asset', node.id, 'CMDB asset');
  const observations = node.observations || [];
  el.querySelector('.hades-window-body').innerHTML = `<div><h2>${esc(node.name || node.hostname || node.id)}</h2><p>${esc(node.resolution_state || 'canonical')} · confidence ${esc(node.confidence)}</p><h3>Identifiers</h3><pre>${esc(JSON.stringify(node.identifiers || [], null, 2))}</pre><h3>Observations / provenance</h3><pre>${esc(JSON.stringify(observations, null, 2))}</pre></div>`;
  return el;
}
export async function openHousehold(){
  const el=panel('household-panel','Household','<p>Loading Household…</p>');
  const r=await fetch('/api/inventory/items?domain=household&include_archived=false'); const d=await r.json();
  el.querySelector('.hades-window-body').innerHTML=`<div><h2>Household</h2><p>Kitchen & Pantry · Stock · Recipes · Locations · Intake</p><div>${(d.items||[]).map(x=>`<button class="list-item hades-entity-link" data-id="${esc(x.id)}"><span>${esc(x.name)}</span><small>${esc(x.category||'item')}</small></button>`).join('')||'<p>No household items yet.</p>'}</div>`;
  bindEntityLinks(el, '.hades-entity-link', openHouseholdItem);
  return el;
}
export async function openItAssets(){
  const el=panel('it-assets-panel','IT Assets','<p>Loading IT Assets…</p>');
  const [items,net]=await Promise.all([fetch('/api/inventory/items?domain=it&include_archived=false').then(r=>r.json()),fetch('/api/network/map').then(r=>r.json())]);
  el.querySelector('.hades-window-body').innerHTML=`<div><h2>IT Assets</h2><p>Computers · Components · Network Devices · Discovered / Unidentified</p><h3>Inventory</h3>${(items.items||[]).map(x=>`<button class="list-item hades-entity-link" data-id="${esc(x.id)}">${esc(x.name)} <small>${esc(x.model||x.category||'asset')}</small></button>`).join('')||'<p>No user-facing IT assets yet.</p>'}<h3>CMDB-backed devices</h3><p>${(net.nodes||[]).length} canonical nodes · ${esc(net.identity_rule||'')}</p>${(net.nodes||[]).map(x=>`<button class="list-item hades-cmdb-link" data-id="${esc(x.id)}">${esc(x.name||x.hostname||x.id)} <small>${esc(x.resolution_state||'unidentified')}</small></button>`).join('')}</div>`;
  bindEntityLinks(el, '.hades-entity-link', openItAsset);
  bindEntityLinks(el, '.hades-cmdb-link', id => (net.nodes||[]).find(x => x.id === id) && openCmdbAsset((net.nodes||[]).find(x => x.id === id)));
  return el;
}
export async function openNetwork(){
  const el=panel('network-panel','Network','<p>Loading Network Map…</p>');
  const d=await fetch('/api/network/map').then(r=>r.json());
  el.querySelector('.hades-window-body').innerHTML=`<div><h2>Network</h2><p>Logical topology · Devices · Subnets · Services · Discovery</p><p class="muted">${esc(d.source||'CMDB')} · ${esc(d.identity_rule||'')}</p><div>${(d.nodes||[]).map(x=>`<button class="list-item hades-cmdb-link" data-id="${esc(x.id)}"><span>${esc(x.name||x.hostname||x.id)}</span><small>${esc(x.resolution_state||'unidentified')}</small></button>`).join('')||'<p>No CMDB nodes observed.</p>'}</div></div>`;
  bindEntityLinks(el, '.hades-cmdb-link', id => (d.nodes||[]).find(x => x.id === id) && openCmdbAsset((d.nodes||[]).find(x => x.id === id)));
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
