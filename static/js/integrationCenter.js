import { openView, registerView } from './workspaceWindowManager.js';
import { errorState, loadingState, moduleHeader, statusBadge } from './ui-components.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function load(el) {
  const body = el.querySelector('.hades-window-body');
  body.innerHTML = loadingState('Loading Integration Center…');
  try {
    const [integrations, permissions, plaid, connection] = await Promise.all([
      fetch('/api/setup-center/integrations', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Integration projection unavailable'); return data; }),
      fetch('/api/setup-center/permissions', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Authority projection unavailable'); return data; }),
      fetch('/api/finance/plaid/items', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Finance connection unavailable'); return data; }),
      fetch('/api/finance/plaid/connection', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Finance lifecycle unavailable'); return data; }),
    ]);
    const cards=(integrations.integrations||[]).map(item => `<article class="hades-record-card"><div><strong>${esc(item.title)}</strong><p>${esc(item.capabilities?.join(', ')||'No capabilities recorded')}</p><small>Last success: ${esc(item.last_success||'not recorded')} · secrets hidden</small></div><div>${statusBadge(item.connection,item.connection==='CONNECTED'?'success':item.connection==='DEGRADED'?'warning':'info')}</div></article>`).join('') || '<p class="muted">No canonical integrations are registered.</p>';
    const items = plaid.items || [];
    const lifecycle = connection.connection || {};
    const plaidCards = items.map(item => `<article class="hades-record-card"><div><strong>${esc(item.institution_name || 'Plaid account')}</strong><p>Read-only Finance sync · ${esc(item.lifecycle_state || item.sync_status || 'unknown')}</p><small>Last success: ${esc(item.last_successful_sync_at || 'not yet')} · secrets hidden</small></div><div>${statusBadge(item.lifecycle_state || item.sync_status || 'NOT_CONFIGURED', item.lifecycle_state === 'HEALTHY' ? 'success' : ['DEGRADED','RECONNECT_REQUIRED'].includes(item.lifecycle_state) ? 'warning' : 'info')}<button type="button" class="integration-plaid-sync" data-item-id="${esc(item.item_id)}">Sync now</button></div></article>`).join('');
    const reconnectId = lifecycle.lifecycle_state === 'RECONNECT_REQUIRED' ? lifecycle.id : '';
    body.innerHTML=`${moduleHeader({icon:'integrations',title:'Integration Center',description:'Connection health and capability readiness. Secrets and account numbers never appear here.',primary:'Refresh',primaryId:'integration-center-refresh'})}<p class="muted">${esc((permissions.policy_source||'Canonical policy services remain authoritative.'))}</p><section class="setup-center-category"><h3>Connected integrations</h3><div class="hades-record-list">${cards}</div></section><section class="setup-center-category"><h3>Finance / Plaid</h3><p class="muted">${esc(lifecycle.lifecycle_state === 'RECONNECT_REQUIRED' ? 'Your Finance connection needs attention.' : lifecycle.lifecycle_state === 'HEALTHY' ? 'Finance is synchronized and read-only.' : 'Connect a bank through Plaid Link. HADES imports read-only transaction data; it cannot move money.')}</p><div class="hades-record-list">${plaidCards || '<p class="muted">No Plaid account connected.</p>'}</div><button type="button" class="integration-plaid-connect" id="integration-plaid-connect" data-reconnect-id="${esc(reconnectId)}">${reconnectId ? 'Reconnect Plaid' : items.length ? 'Connect another account' : 'Connect Plaid'}</button><p id="integration-plaid-status" class="muted" role="status"></p></section>`;
    body.querySelector('#integration-center-refresh').onclick=()=>load(el);
    body.querySelectorAll('.integration-plaid-sync').forEach(button => button.onclick=async()=>{button.disabled=true;button.textContent='Syncing…';try{await fetch(`/api/finance/plaid/items/${encodeURIComponent(button.dataset.itemId)}/sync`,{method:'POST',credentials:'same-origin'});await load(el);}catch(error){body.querySelector('#integration-plaid-status').textContent=error.message;button.disabled=false;button.textContent='Sync now';}});
    body.querySelector('#integration-plaid-connect').onclick=()=>connectPlaid(el);
  } catch (error) { body.innerHTML=errorState(error.message,'integration-center-retry'); body.querySelector('#integration-center-retry')?.addEventListener('click',()=>load(el)); }
}

async function connectPlaid(el) {
  const status = el.querySelector('#integration-plaid-status');
  if (!window.Plaid?.create) { status.textContent='Plaid Link is unavailable right now. Try again after the service is ready.'; return; }
  const button = el.querySelector('#integration-plaid-connect');
  button.disabled = true; status.textContent = 'Opening secure bank connection…';
  try {
    const reconnectId = button.dataset.reconnectId;
    const response = await fetch('/api/finance/plaid/link-token'+(reconnectId ? `?connection_id=${encodeURIComponent(reconnectId)}` : ''), {method:'POST', credentials:'same-origin'});
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || 'Could not start Plaid Link');
    const temporaryToken = data.link_token;
    const handler = window.Plaid.create({token: temporaryToken, onSuccess: async publicToken => {
      status.textContent = 'Finishing secure connection and syncing transactions…';
      const exchange = await fetch('/api/finance/plaid/link-exchange', {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body:JSON.stringify({public_token:publicToken, link_token:temporaryToken, authorization_state:data.authorization_state})});
      const result = await exchange.json();
      if (!exchange.ok) throw Error(result.detail || 'Could not finish the connection');
      await load(el);
    }, onExit: error => { if (error?.error_code) status.textContent = 'Connection cancelled. No financial changes were made.'; button.disabled=false; }});
    handler.open();
  } catch (error) { status.textContent = error.message; button.disabled = false; }
}

export function openIntegrationCenter(){const el=openView('integration-center',null,'Integration Center',loadingState());load(el);return el;}
registerView('integration-center',()=>openIntegrationCenter());
export default {openIntegrationCenter};
