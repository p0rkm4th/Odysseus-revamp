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
  const lots = d.lots || [];
  const stock = lots.length ? `<ul>${lots.map(lot => `<li><strong>${esc(lot.quantity)} ${esc(lot.unit || item.default_unit || 'each')}</strong>${lot.location_name ? ` · ${esc(lot.location_name)}` : ''}${lot.expiry_date ? ` · expires ${esc(lot.expiry_date)}` : ''}</li>`).join('')}</ul>` : '<p class="hades-empty-state">No stock is recorded for this item.</p>';
  el.querySelector('.hades-window-body').innerHTML = `<div><h2>${esc(item.name || 'Household item')}</h2><p>${esc(item.category || 'household')} · ${esc(item.location_name || 'No location')}</p><p>${esc(item.description || 'No description')}</p><h3>Stock</h3>${stock}</div>`;
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
  const pending = node.resolution_state === 'pending_candidate';
  const unidentified = node.resolution_state === 'unidentified';
  const actions = pending || unidentified ? `<section class="hades-detail-section"><h3>Owner reconciliation</h3><p class="muted">This observation is evidence, not canonical identity. Explicit owner confirmation is required.</p><div class="hades-inline-actions"><button class="list-item" data-cmdb-confirm>Confirm${unidentified ? ' and name' : ''}</button><button class="list-item" data-cmdb-reject>Reject</button></div><p class="muted" data-cmdb-message></p></section>` : '';
  el.querySelector('.hades-window-body').innerHTML = `<div><h2>${esc(node.name || node.hostname || node.id)}</h2><p>${esc(node.resolution_state || 'canonical')} · confidence ${esc(node.confidence)}</p>${actions}<h3>Identifiers</h3><pre>${esc(JSON.stringify(node.identifiers || [], null, 2))}</pre><h3>Observations / provenance</h3><pre>${esc(JSON.stringify(observations, null, 2))}</pre></div>`;
  const reconcile = async (decision) => {
    const name = decision === 'reject' ? undefined : (
      decision === 'create' || (decision === 'confirm' && unidentified)
        ? window.prompt('Name this asset') : window.prompt('Optional asset name', node.name || '')
    );
    if ((decision === 'create' || (decision === 'confirm' && unidentified)) && !name?.trim()) return;
    const response = await fetch('/api/network/assets/reconcile', {
      method: 'POST', credentials: 'same-origin',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({candidate: node.id, decision, name: name?.trim() || undefined, type: node.type || 'network_device'}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Asset reconciliation failed');
    await openNetwork();
    return result;
  };
  el.querySelector('[data-cmdb-confirm]')?.addEventListener('click', async () => {
    const message = el.querySelector('[data-cmdb-message]');
    try { await reconcile('confirm'); message.textContent = 'Asset reconciled.'; } catch (error) { message.textContent = error.message; }
  });
  el.querySelector('[data-cmdb-reject]')?.addEventListener('click', async () => {
    const message = el.querySelector('[data-cmdb-message]');
    try { await reconcile('reject'); message.textContent = 'Candidate rejected.'; } catch (error) { message.textContent = error.message; }
  });
  return el;
}
export async function openHousehold(){
  const el=panel('household-panel','Household','<p>Loading Household…</p>');
  try {
    const d=await fetch('/api/inventory/overview?expiry_days=30',{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(new Error('Household overview unavailable')));
    const items=d.items||[], locations=d.locations||[], low=d.low_stock||[], expiring=d.expiring_lots||[], drafts=d.pending_intake||[], history=d.recent_activity||[];
    const metric=(label,value)=>`<div class="hades-summary-metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-dossier">
      <header class="hades-module-header"><div><h2>Household</h2><p>Kitchen, pantry, stock, recipes, and reviewable intake</p></div><span class="hades-status-badge">Canonical inventory</span></header>
      <div class="hades-summary-metrics">${metric('Items',d.item_count||0)}${metric('Recipes',d.recipe_count||0)}${metric('Low stock',low.length)}${metric('Expiring',expiring.length)}${metric('Pending intake',drafts.length)}</div>
      <section class="hades-detail-section"><h3>Locations</h3>${locations.length?`<div class="hades-summary-metrics">${locations.map(x=>metric(x.name,`${x.item_count} item${x.item_count===1?'':'s'} · ${x.stock_quantity}`)).join('')}</div>`:'<p class="hades-empty-state">No named storage locations are recorded yet.</p>'}</section>
      <section class="hades-detail-section"><h3>Items</h3><div>${items.map(x=>`<button class="list-item hades-entity-link" data-id="${esc(x.id)}"><span>${esc(x.name)}</span><small>${esc(x.category||x.item_kind||'item')} · ${esc(x.stock_quantity||'0')} ${esc(x.default_unit||'each')}${x.location_name?` · ${esc(x.location_name)}`:''}</small></button>`).join('')||'<p class="hades-empty-state">No household items yet. Use Inventory intake to add a reviewed item.</p>'}</div></section>
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
    const userItems=items.items||[], nodes=net.nodes||[], canonical=nodes.filter(x=>x.canonical===true), pending=nodes.filter(x=>x.resolution_state==='pending_candidate'), unidentified=nodes.filter(x=>x.resolution_state==='unidentified');
    const metric=(label,value)=>`<div class="hades-summary-metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-dossier">
      <header class="hades-module-header"><div><h2>IT Assets</h2><p>Inventory assets, CMDB identities, observations, and reconciliation</p></div><span class="hades-status-badge">Two canonical sources</span></header>
      <div class="hades-summary-metrics">${metric('Inventory assets',userItems.length)}${metric('CMDB assets',canonical.length)}${metric('Pending candidates',pending.length)}${metric('Unidentified',unidentified.length)}${metric('Observed nodes',nodes.length)}</div>
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
    const nodes=d.nodes||[], edges=d.edges||[], canonical=nodes.filter(x=>x.canonical===true), pending=nodes.filter(x=>x.resolution_state==='pending_candidate'), unidentified=nodes.filter(x=>x.resolution_state==='unidentified');
    const metric=(label,value)=>`<div class="hades-summary-metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-dossier">
      <header class="hades-module-header"><div><h2>Network</h2><p>Devices, observations, topology, and bounded discovery</p></div><span class="hades-status-badge">${esc(d.source||'CMDB')}</span></header>
      <div class="hades-summary-metrics">${metric('Nodes',nodes.length)}${metric('Canonical',canonical.length)}${metric('Pending candidates',pending.length)}${metric('Unidentified',unidentified.length)}${metric('Relationships',edges.length)}</div>
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
export async function openSmartHome(){
  const el=panel('smart-home-panel','Smart Home','<p>Loading Home Assistant projection…</p>');
  try {
    const d=await fetch('/api/home-assistant/overview',{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(new Error('Smart Home overview unavailable')));
    const metric=(label,value)=>`<div class="hades-summary-metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
    const domains=Object.entries(d.domains||{});
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-dossier">
      <header class="hades-module-header"><div><h2>Smart Home</h2><p>Home Assistant rooms, devices, entities, and read-only state</p></div><span class="hades-status-badge">${esc(d.status||'unknown')}</span></header>
      <div class="hades-summary-metrics">${metric('Configured',d.configured?'Yes':'No')}${metric('Entities',d.entities||0)}${metric('Domains',domains.length)}${metric('Authority',d.authority_unchanged?'Existing':'Unknown')}</div>
      <section class="hades-detail-section"><h3>Home Assistant</h3>${d.configured?`<p>Health is projected through the existing generic integration API boundary.</p><p class="muted">${esc(d.source||'generic integration')} · read-only projection · entity state is not copied into a second canonical store.</p>`:'<p class="hades-empty-state">Home Assistant is not configured. Configure it from Integrations when credentials and owner authorization are available.</p>'}</section>
      <section class="hades-detail-section"><h3>Entities by domain</h3>${domains.length?`<ul>${domains.map(([domain,count])=>`<li><strong>${esc(domain)}</strong> · ${esc(count)} entities</li>`).join('')}</ul>`:'<p class="hades-empty-state">No Home Assistant entities are projected.</p>'}</section>
      <section class="hades-detail-section"><h3>Sample entity references</h3>${(d.sample_entities||[]).length?`<ul>${d.sample_entities.map(x=>`<li><code>${esc(x)}</code></li>`).join('')}</ul>`:'<p class="hades-empty-state">No entity references available.</p>'}</section>
      <p class="muted">State-changing smart-home actions are not exposed by this projection; they remain subject to existing ActionSpec, policy, approval, and integration authority.</p>
    </div>`;
  } catch (error) {
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-error-state">${esc(error.message)} <button class="list-item" data-retry-smart-home>Retry</button></div>`;
    el.querySelector('[data-retry-smart-home]')?.addEventListener('click', () => openSmartHome());
  }
  return el;
}
export async function openCommunications(){
  const el=panel('communications-panel','Communications','<p>Loading Email, Calendar, and Contacts projection…</p>');
  try {
    const d=await fetch('/api/communications/overview',{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(new Error('Communications overview unavailable')));
    const email=d.email||{}, calendar=d.calendar||{}, events=calendar.events||[];
    const metric=(label,value)=>`<div class="hades-summary-metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-dossier">
      <header class="hades-module-header"><div><h2>Communications</h2><p>Email, Calendar, Contacts, and owner-scoped follow-up context</p></div><span class="hades-status-badge">Canonical projections</span></header>
      <div class="hades-summary-metrics">${metric('Email accounts',email.configured||0)}${metric('Enabled',email.enabled||0)}${metric('Calendars',calendar.calendars||0)}${metric('Next 14 days',calendar.upcoming_14_days||0)}</div>
      <section class="hades-detail-section"><h3>Email</h3>${(email.accounts||[]).length?`<ul>${email.accounts.map(x=>`<li>${esc(x.name||x.id)} · ${x.enabled?'enabled':'disabled'}${x.default?' · default':''}</li>`).join('')}</ul>`:'<p class="hades-empty-state">No owner-scoped email accounts are configured.</p>'}</section>
      <section class="hades-detail-section"><h3>Upcoming Calendar</h3>${events.length?`<ul>${events.map(x=>`<li>${esc(x.summary||'Untitled event')} · ${esc(x.dtstart)}</li>`).join('')}</ul>`:'<p class="hades-empty-state">No upcoming events are projected for the next 14 days.</p>'}</section>
      <section class="hades-detail-section"><h3>Contacts</h3><p class="muted">${esc(d.contacts?.canonical_store||'Canonical Contacts store')} remains separate; this overview does not copy contact records.</p></section>
      <p class="muted">Source: ${esc(d.source||'canonical integrations')} · Email and Calendar windows remain the authoritative detailed views.</p>
    </div>`;
  } catch (error) {
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-error-state">${esc(error.message)} <button class="list-item" data-retry-communications>Retry</button></div>`;
    el.querySelector('[data-retry-communications]')?.addEventListener('click', () => openCommunications());
  }
  return el;
}
export async function openTelegram(){
  const el=panel('telegram-panel','Telegram','<p>Loading Telegram transport status…</p>');
  const load=async()=>{
    const d=await fetch('/api/telegram/status',{credentials:'same-origin'}).then(r=>r.ok?r.json():Promise.reject(new Error('Telegram status unavailable')));
    const connected=!!d.connected;
    const metric=(label,value)=>`<div class="hades-summary-metric"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`;
    el.querySelector('.hades-window-body').innerHTML=`<div class="hades-dossier">
      <header class="hades-module-header"><div><h2>Telegram</h2><p>Owner-paired transport, continuity, approvals, and delivery health</p></div><span class="hades-status-badge">${connected?'connected':'not paired'}</span></header>
      <div class="hades-summary-metrics">${metric('Connection',connected?'Active':'Inactive')}${metric('Pending pairing',d.pending_pairing?'Yes':'No')}${metric('Bound sessions',(d.sessions||[]).length)}${metric('Owner',d.display_username||'—')}</div>
      <section class="hades-detail-section"><h3>Pairing</h3><p>${connected?'Telegram is paired to this owner through the existing private-chat boundary.':'Generate a short-lived pairing code, then complete pairing from the Telegram private chat.'}</p><div class="hades-inline-actions">${connected?'<button class="list-item" data-telegram-disconnect>Disconnect</button>':'<button class="list-item" data-telegram-pair>Generate pairing code</button>'}</div><p class="muted" data-telegram-message></p></section>
      <section class="hades-detail-section"><h3>Continuity sessions</h3>${(d.sessions||[]).length?`<ul>${d.sessions.map(x=>`<li><code>${esc(x.odysseus_session_id)}</code> · revision ${esc(x.revision)} · updated ${esc(x.updated_at||'')}</li>`).join('')}</ul>`:'<p class="hades-empty-state">No Telegram conversation is currently bound to an Odysseus session.</p>'}</section>
      <p class="muted">Owner scope, private-chat restriction, replay protection, approvals, and transport authority remain in the existing Telegram store/runtime.</p>
    </div>`;
    el.querySelector('[data-telegram-pair]')?.addEventListener('click',async()=>{
      const response=await fetch('/api/telegram/pairing-codes',{method:'POST',credentials:'same-origin',headers:{'content-type':'application/json'},body:JSON.stringify({lifetime_seconds:600})});
      const result=await response.json(); const message=el.querySelector('[data-telegram-message]');
      message.textContent=response.ok?`Pairing code: ${result.pairing_code} · expires ${result.expires_at}`:(result.detail||'Pairing code unavailable');
    });
    el.querySelector('[data-telegram-disconnect]')?.addEventListener('click',async()=>{await fetch('/api/telegram/connection',{method:'DELETE',credentials:'same-origin'});await load();});
  };
  try { await load(); } catch (error) { el.querySelector('.hades-window-body').innerHTML=`<div class="hades-error-state">${esc(error.message)} <button class="list-item" data-retry-telegram>Retry</button></div>`; el.querySelector('[data-retry-telegram]')?.addEventListener('click',()=>openTelegram()); }
  return el;
}
export async function openDeveloper(){
  const el=panel('developer-panel','Developer','<p>Loading Developer Mode…</p>');
  const [d, build] = await Promise.all([fetch('/api/developer/yolo/status').then(r=>r.json()), fetch('/api/version').then(r=>r.json()).catch(()=>({}))]);
  const lease=d.lease; const content=`<p><b>Workspace YOLO</b></p><p>Scope: <code>${esc(d.workspace)}</code><br>Root: NO · Docker: NO<br>Authority: arbitrary workspace Bash</p><p>${lease?`Active until ${esc(lease.expires_at)} <button id="revoke-yolo">Revoke</button>`:'Inactive — requires explicit owner activation.'}</p>${lease?'': '<button id="grant-yolo">Enable for 30 minutes</button>'}`;
  const theme = window.themeModule?.getSaved?.() || {};
  const diagnostics = `<section class="hades-detail-section"><h3>Runtime diagnostics</h3><dl class="hades-diagnostic-list"><dt>Source commit</dt><dd>${esc(build.source_commit || 'unknown')}</dd><dt>Image</dt><dd>${esc(build.image_id || 'unknown')}</dd><dt>Frontend build</dt><dd>${esc(build.frontend_build_id || 'unknown')}</dd><dt>UI state schema</dt><dd>${esc(build.ui_state_schema_version || 'unknown')}</dd><dt>Active theme</dt><dd>${esc(theme.name || 'default')}</dd></dl></section>`;
  el.querySelector('.hades-window-body').innerHTML=`<div><h2>Developer Mode</h2>${diagnostics}${content}</div>`;
  if (lease) el.querySelector('#revoke-yolo').onclick=async()=>{await fetch('/api/developer/yolo/revoke',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({lease_id:lease.id})});openDeveloper();};
  else el.querySelector('#grant-yolo').onclick=async()=>{await fetch('/api/developer/yolo/grant',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({duration_seconds:1800})});openDeveloper();};
  return el;
}
registerView('household-panel', () => openHousehold());
registerView('it-assets-panel', () => openItAssets());
registerView('network-panel', () => openNetwork());
registerView('developer-panel', () => openDeveloper());
