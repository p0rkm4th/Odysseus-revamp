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
  try {
    const d=await fetch('/api/inventory/overview?expiry_days=30',{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(new Error('Household overview unavailable')));
    const items=d.items||[], low=d.low_stock||[], expiring=d.expiring_lots||[], drafts=d.pending_intake||[], history=d.recent_activity||[];
    const metric=(label,value)=>`<div class="hades-summary-metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-dossier">
      <header class="hades-module-header"><div><h2>Household</h2><p>Kitchen, pantry, stock, recipes, and reviewable intake</p></div><span class="hades-status-badge">Canonical inventory</span></header>
      <div class="hades-summary-metrics">${metric('Items',d.item_count||0)}${metric('Recipes',d.recipe_count||0)}${metric('Low stock',low.length)}${metric('Expiring',expiring.length)}${metric('Pending intake',drafts.length)}</div>
      <section class="hades-detail-section"><h3>Items</h3><div>${items.map(x=>`<button class="list-item hades-entity-link" data-id="${esc(x.id)}"><span>${esc(x.name)}</span><small>${esc(x.category||x.item_kind||'item')} · ${esc(x.stock_quantity||'0')} ${esc(x.default_unit||'each')}</small></button>`).join('')||'<p class="hades-empty-state">No household items yet. Use Inventory intake to add a reviewed item.</p>'}</div></section>
      <section class="hades-detail-section"><h3>Needs attention</h3>${low.length?`<ul>${low.map(x=>`<li>${esc(x.item.name)} — ${esc(x.quantity)} ${esc(x.item.default_unit)} (reorder at ${esc(x.reorder_point)})</li>`).join('')}</ul>`:'<p class="hades-empty-state">No items are below their reorder point.</p>'}${expiring.length?`<h4>Expiring within 30 days</h4><ul>${expiring.map(x=>`<li>${esc(x.item.name)} — ${esc(x.lot.expiry_date||'unknown')} (${esc(x.status)})</li>`).join('')}</ul>`:''}</section>
      <section class="hades-detail-section"><h3>Reviewable intake</h3>${drafts.length?`<ul>${drafts.map(x=>`<li>${esc(x.source_type)} draft <code>${esc(x.id)}</code> · ${esc(x.status)}</li>`).join('')}</ul>`:'<p class="hades-empty-state">No pending intake drafts.</p>'}</section>
      <section class="hades-detail-section"><h3>Recent activity</h3>${history.length?`<ul>${history.map(x=>`<li>${esc(x.movement.reason)} ${esc(x.movement.quantity_delta)} ${esc(x.movement.unit)} · ${esc(x.item?.name||'item')} <small>${esc(x.movement.occurred_at||'')}</small></li>`).join('')}</ul>`:'<p class="hades-empty-state">No stock movement history yet.</p>'}</section>
      <p class="muted">Projection: ${esc(d.canonical_store)} · computed ${esc(d.freshness?.computed_at||'')}</p>
    </div>`;
    bindEntityLinks(el, '.hades-entity-link', openHouseholdItem);
  } catch (error) {
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-error-state">${esc(error.message)} <button class="list-item" data-retry-household>Retry</button></div>`;
    el.querySelector('[data-retry-household]')?.addEventListener('click', () => openHousehold());
  }
  return el;
}
export async function openItAssets(){
  const el=panel('it-assets-panel','IT Assets','<p>Loading IT Assets…</p>');
  try {
    const [items,net]=await Promise.all([
      fetch('/api/inventory/items?domain=it&include_archived=false',{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(new Error('IT inventory unavailable'))),
      fetch('/api/network/map',{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(new Error('CMDB projection unavailable'))),
    ]);
    const userItems=items.items||[], nodes=net.nodes||[], canonical=nodes.filter(x=>x.canonical!==false), unidentified=nodes.filter(x=>x.resolution_state==='unidentified');
    const metric=(label,value)=>`<div class="hades-summary-metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-dossier">
      <header class="hades-module-header"><div><h2>IT Assets</h2><p>Inventory assets, CMDB identities, observations, and reconciliation</p></div><span class="hades-status-badge">Two canonical sources</span></header>
      <div class="hades-summary-metrics">${metric('Inventory assets',userItems.length)}${metric('CMDB assets',canonical.length)}${metric('Unidentified',unidentified.length)}${metric('Observed nodes',nodes.length)}</div>
      <section class="hades-detail-section"><h3>Inventory assets</h3><p class="muted">User-entered assets remain in InventoryService; they are not silently merged with CMDB identities.</p><div>${userItems.map(x=>`<button class="list-item hades-entity-link" data-id="${esc(x.id)}"><span>${esc(x.name)}</span><small>${esc(x.model||x.category||'asset')} · ${esc(x.manufacturer||'')}</small></button>`).join('')||'<p class="hades-empty-state">No user-facing IT assets yet.</p>'}</div></section>
      <section class="hades-detail-section"><h3>CMDB-backed devices</h3><p class="muted">${esc(net.identity_rule||'IP addresses remain observations; identity requires stronger evidence.')}</p><div>${nodes.map(x=>`<button class="list-item hades-cmdb-link" data-id="${esc(x.id)}"><span>${esc(x.name||x.hostname||x.id)}</span><small>${esc(x.resolution_state||'unidentified')} · confidence ${esc(x.confidence??'—')}</small></button>`).join('')||'<p class="hades-empty-state">No CMDB observations yet.</p>'}</div></section>
      <p class="muted">CMDB source: ${esc(net.source||'canonical_cmdb')} · unidentified observations remain non-canonical until reconciled.</p>
    </div>`;
    bindEntityLinks(el, '.hades-entity-link', openItAsset);
    bindEntityLinks(el, '.hades-cmdb-link', id => { const node=nodes.find(x => x.id === id); if (node) openCmdbAsset(node); });
  } catch (error) {
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-error-state">${esc(error.message)} <button class="list-item" data-retry-assets>Retry</button></div>`;
    el.querySelector('[data-retry-assets]')?.addEventListener('click', () => openItAssets());
  }
  return el;
}
export async function openNetwork(){
  const el=panel('network-panel','Network','<p>Loading Network Map…</p>');
  try {
    const d=await fetch('/api/network/map',{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(new Error('Network map unavailable')));
    const nodes=d.nodes||[], edges=d.edges||[], canonical=nodes.filter(x=>x.canonical!==false), unidentified=nodes.filter(x=>x.resolution_state==='unidentified');
    const metric=(label,value)=>`<div class="hades-summary-metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-dossier">
      <header class="hades-module-header"><div><h2>Network</h2><p>Devices, observations, topology, and bounded discovery</p></div><span class="hades-status-badge">${esc(d.source||'CMDB')}</span></header>
      <div class="hades-summary-metrics">${metric('Nodes',nodes.length)}${metric('Canonical',canonical.length)}${metric('Unidentified',unidentified.length)}${metric('Relationships',edges.length)}</div>
      <section class="hades-detail-section"><h3>Identity and provenance</h3><p class="muted">${esc(d.identity_rule||'IP addresses remain observations; no IP-only merge.')}</p></section>
      <section class="hades-detail-section"><h3>Devices</h3><div>${nodes.map(x=>`<button class="list-item hades-cmdb-link" data-id="${esc(x.id)}"><span>${esc(x.name||x.hostname||x.id)}</span><small>${esc(x.resolution_state||'unidentified')} · ${esc(x.status||'observed')} · confidence ${esc(x.confidence??'—')}</small></button>`).join('')||'<p class="hades-empty-state">No CMDB nodes observed yet.</p>'}</div></section>
      <section class="hades-detail-section"><h3>Relationships</h3>${edges.length?`<p>${esc(edges.length)} active evidence-backed relationship${edges.length===1?'':'s'} projected from CMDB.</p>`:'<p class="hades-empty-state">No active relationships are projected.</p>'}</section>
    </div>`;
    bindEntityLinks(el, '.hades-cmdb-link', id => { const node=nodes.find(x => x.id === id); if (node) openCmdbAsset(node); });
  } catch (error) {
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-error-state">${esc(error.message)} <button class="list-item" data-retry-network>Retry</button></div>`;
    el.querySelector('[data-retry-network]')?.addEventListener('click', () => openNetwork());
  }
  return el;
}
export async function openHomelab(){
  const el=panel('homelab-panel','Homelab','<p>Loading Homelab status…</p>');
  try {
    const [self,map]=await Promise.all([
      fetch('/api/hades/self',{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(new Error('Homelab status unavailable'))),
      fetch('/api/network/map',{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(new Error('Network projection unavailable'))),
    ]);
    const runtime=self.runtime||{}, capabilities=self.capabilities||[], homelab=capabilities.find(x=>x.capability==='homelab.manage')||{status:'available_if_authorized',authority:'existing privileged broker'};
    const broker=runtime.broker_health||{};
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-dossier">
      <header class="hades-module-header"><div><h2>Homelab</h2><p>Bounded host operations, services, storage, containers, and network discovery</p></div><span class="hades-status-badge">${esc(homelab.status||'unknown')}</span></header>
      <div class="hades-summary-metrics"><div class="hades-summary-metric"><small>Capability</small><strong>${esc(homelab.capability||'homelab.manage')}</strong></div><div class="hades-summary-metric"><small>Broker</small><strong>${esc(broker.status||'unknown')}</strong></div><div class="hades-summary-metric"><small>CMDB nodes</small><strong>${esc((map.nodes||[]).length)}</strong></div><div class="hades-summary-metric"><small>Execution</small><strong>${esc(runtime.execution_environment?.runtime||'projected')}</strong></div></div>
      <section class="hades-detail-section"><h3>Authority and health</h3><p>${esc(homelab.description||'Bounded local Homelab capability')}</p><p class="muted">${esc(homelab.authority||broker.authority||'Existing policy and privileged broker remain authoritative.')}. Actions require their existing ActionSpec, policy, and approval paths.</p></section>
      <section class="hades-detail-section"><h3>Available first-class areas</h3><ul><li>Host and service inspection</li><li>Bounded private-network discovery through the host broker</li><li>Scoped diagnostic planning and approved operations</li><li>CMDB-backed observations and Network Map</li></ul></section>
      <section class="hades-detail-section"><h3>Network observation</h3><p>${esc((map.nodes||[]).length)} nodes and ${esc((map.edges||[]).length)} relationships are currently projected from ${esc(map.source||'canonical CMDB')}.</p><p class="muted">${esc(map.identity_rule||'IP addresses remain observations; no IP-only merge.')}</p></section>
    </div>`;
  } catch (error) {
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-error-state">${esc(error.message)} <button class="list-item" data-retry-homelab>Retry</button></div>`;
    el.querySelector('[data-retry-homelab]')?.addEventListener('click', () => openHomelab());
  }
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
