import { openView, registerView } from './workspaceWindowManager.js';
import { errorState, loadingState, moduleHeader, statusBadge } from './ui-components.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function load(el) {
  const body = el.querySelector('.hades-window-body');
  body.innerHTML = loadingState('Loading Integration Center…');
  try {
    const [integrations, permissions, plaid, connection, plaidConfig, financeAccounts] = await Promise.all([
      fetch('/api/setup-center/integrations', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Integration projection unavailable'); return data; }),
      fetch('/api/setup-center/permissions', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Authority projection unavailable'); return data; }),
      fetch('/api/finance/plaid/items', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Finance connection unavailable'); return data; }),
      fetch('/api/finance/plaid/connection', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Finance lifecycle unavailable'); return data; }),
      fetch('/api/finance/plaid/config', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Plaid configuration unavailable'); return data; }),
      fetch('/api/finance/accounts', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Finance accounts unavailable'); return data; }),
    ]);
    const cards=(integrations.integrations||[]).map(item => `<article class="hades-record-card"><div><strong>${esc(item.title)}</strong><p>${esc(item.capabilities?.join(', ')||'No capabilities recorded')}</p><small>Last success: ${esc(item.last_success||'not recorded')} · secrets hidden</small></div><div>${statusBadge(item.connection,item.connection==='CONNECTED'?'success':item.connection==='DEGRADED'?'warning':'info')}</div></article>`).join('') || '<p class="muted">No canonical integrations are registered.</p>';
    const items = plaid.items || [];
    const lifecycle = connection.connection || {};
    const connectionRows = Array.isArray(lifecycle.connections) ? lifecycle.connections : [];
    const itemByConnection = new Map(items.filter(item => item.connection_id).map(item => [item.connection_id, item]));
    const plaidCards = items.map(item => {
      const state = item.lifecycle_state || item.sync_status || 'UNKNOWN';
      const reconnect = state === 'RECONNECT_REQUIRED'
        ? `<button type="button" class="integration-plaid-reconnect" data-connection-id="${esc(item.connection_id)}">Reconnect</button>`
        : '';
      // Reconnect is a provider-authorization operation, not a sync retry.
      // Never present both controls for an unhealthy authorization, which
      // would invite an invalid-token retry and blur the recovery contract.
      const sync = state === 'RECONNECT_REQUIRED'
        ? ''
        : `<button type="button" class="integration-plaid-sync" data-item-id="${esc(item.item_id)}">${state === 'DEGRADED' ? 'Retry sync' : 'Sync now'}</button>`;
      return `<article class="hades-record-card"><div><strong>${esc(item.institution_name || 'Plaid account')}</strong><p>Read-only Finance sync · ${esc(state)}</p><small>Last success: ${esc(item.last_successful_sync_at || 'not yet')} · secrets hidden</small>${item.last_error_classification ? `<small class="muted">Needs attention: ${esc(item.last_error_classification)}</small>` : ''}</div><div>${statusBadge(state, state === 'HEALTHY' ? 'success' : ['DEGRADED','RECONNECT_REQUIRED'].includes(state) ? 'warning' : 'info')}${sync}${reconnect}</div></article>`;
    }).join('') + connectionRows.filter(row => !itemByConnection.has(row.id)).map(row => {
      const state = row.lifecycle_state || 'AUTHORIZATION_REQUIRED';
      const action = state === 'AUTHORIZATION_IN_PROGRESS' ? 'Resume authorization' : 'Connect Plaid';
      return `<article class="hades-record-card"><div><strong>Plaid connection</strong><p>Read-only Finance sync · ${esc(state)}</p><small>Authorization has not produced a provider item yet · secrets hidden</small>${row.last_error_classification ? `<small class="muted">Needs attention: ${esc(row.last_error_classification)}</small>` : ''}</div><div>${statusBadge(state, state === 'AUTHORIZATION_IN_PROGRESS' ? 'warning' : 'info')}<button type="button" class="integration-plaid-reconnect" data-connection-id="${esc(row.id)}">${action}</button></div></article>`;
    }).join('');
    const csvCards = (financeAccounts.accounts || []).filter(account => account.provider === 'csv').map(account => `<article class="hades-record-card"><div><strong>${esc(account.display_name || 'Local bank export')}</strong><p>Local CSV snapshot · ${esc(account.currency || 'currency not recorded')}</p><small>Imported: ${esc(account.last_synced_at || 'not recorded')} · not a live provider</small></div><div>${statusBadge('IMPORTED', 'success')}</div></article>`).join('');
    const healthy = lifecycle.lifecycle_state === 'HEALTHY';
    const hasUnknownCoverage = items.some(item => !item.last_successful_sync_at);
    const lifecycleMessage = lifecycle.lifecycle_state === 'RECONNECT_REQUIRED'
      ? 'One or more Finance connections need attention; reconnect them from their individual cards.'
      : healthy && !hasUnknownCoverage
        ? 'Finance is synchronized and read-only. Individual connection health is shown below.'
        : 'Finance coverage is not yet complete. Connect or synchronize each account before relying on a requested range.';
    const plaidSetup = plaidConfig.configured
      ? `<p class="muted">Plaid application credentials are configured for ${esc(plaidConfig.environment)}. Secrets remain server-side.</p>`
      : plaidConfig.can_configure
        ? `<form id="integration-plaid-config" class="integration-plaid-config"><h4>Configure Plaid</h4><p class="muted">Create keys in the <a href="https://dashboard.plaid.com/developers/keys" target="_blank" rel="noopener">Plaid Dashboard</a>. They are encrypted before storage and never returned.</p><label>Client ID<input name="client_id" autocomplete="off" required></label><label>Secret<input name="secret" type="password" autocomplete="new-password" required></label><label>Environment<select name="environment"><option value="sandbox">Sandbox</option><option value="development">Development</option><option value="production">Production</option></select></label><label>App name<input name="client_name" value="HADES" maxlength="100"></label><button type="submit">Save Plaid configuration</button></form>`
        : '<p class="muted">Plaid application credentials are not configured. An administrator must configure them before bank authorization can begin.</p>';
    body.innerHTML=`${moduleHeader({icon:'integrations',title:'Integration Center',description:'Connection health and capability readiness. Secrets and account numbers never appear here.',primary:'Refresh',primaryId:'integration-center-refresh'})}<p class="muted">${esc((permissions.policy_source||'Canonical policy services remain authoritative.'))}</p><section class="setup-center-category"><h3>Connected integrations</h3><div class="hades-record-list">${cards}</div></section><section class="setup-center-category"><h3>Finance / Plaid</h3><p class="muted">${esc(lifecycleMessage)}</p>${plaidSetup}<div class="hades-record-list">${plaidCards || '<p class="muted">No Plaid account connected.</p>'}${csvCards}</div><button type="button" class="integration-plaid-connect" id="integration-plaid-connect">${items.length ? 'Connect another account' : 'Connect Plaid'}</button><label class="integration-csv-import">Use a local bank export if Plaid is unavailable <input id="integration-finance-csv" type="file" accept=".csv,text/csv"></label><p class="muted">Accepts common exports with Date/Posted Date plus Amount, or Debit/Credit, and Merchant/Name/Description/Payee columns. CSV imports are owner-scoped snapshots, not live balances; repeated imports are safe.</p><p id="integration-plaid-status" class="muted" role="status"></p></section>`;
    body.querySelector('#integration-center-refresh').onclick=()=>load(el);
    body.querySelectorAll('.integration-plaid-sync').forEach(button => button.onclick=async()=>{button.disabled=true;button.textContent='Syncing…';try{const response=await fetch(`/api/finance/plaid/items/${encodeURIComponent(button.dataset.itemId)}/sync`,{method:'POST',credentials:'same-origin'});const result=await response.json().catch(()=>({}));if(!response.ok)throw Error(result.detail||'Finance synchronization failed');await load(el);}catch(error){body.querySelector('#integration-plaid-status').textContent=error.message;button.disabled=false;button.textContent='Sync now';}});
    body.querySelectorAll('.integration-plaid-reconnect').forEach(button => button.onclick=()=>connectPlaid(el, button.dataset.connectionId));
    body.querySelector('#integration-plaid-connect').onclick=()=>connectPlaid(el);
    body.querySelector('#integration-plaid-config')?.addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget;const status=body.querySelector('#integration-plaid-status');const payload=Object.fromEntries(new FormData(form));status.textContent='Saving encrypted Plaid configuration…';form.querySelector('button').disabled=true;try{const response=await fetch('/api/finance/plaid/config',{method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const result=await response.json().catch(()=>({}));if(!response.ok)throw Error(result.detail||'Could not save Plaid configuration');await load(el);}catch(error){status.textContent=error.message;form.querySelector('button').disabled=false;}});
    body.querySelector('#integration-finance-csv').onchange=async event=>{
      const file=event.target.files?.[0]; if(!file) return;
      const status=body.querySelector('#integration-plaid-status'); status.textContent='Importing the local Finance snapshot…'; event.target.disabled=true;
      try { const csv=await file.text(); const response=await fetch('/api/finance/csv/import',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({csv,source_label:file.name})}); const result=await response.json().catch(()=>({})); if(!response.ok) throw Error(result.detail||'Finance CSV import failed'); const count=result.import?.imported_count ?? 0; await load(el); el.querySelector('#integration-plaid-status').textContent=`Imported ${count} transaction${count === 1 ? '' : 's'} from ${file.name}.`;
      }
      catch(error){ status.textContent=error.message; event.target.disabled=false; }
    };
  } catch (error) { body.innerHTML=errorState(error.message,'integration-center-retry'); body.querySelector('#integration-center-retry')?.addEventListener('click',()=>load(el)); }
}

async function connectPlaid(el, connectionId = '') {
  const status = el.querySelector('#integration-plaid-status');
  if (!window.Plaid?.create) { status.textContent='Plaid Link is unavailable right now. Try again after the service is ready.'; return; }
  const button = el.querySelector('#integration-plaid-connect');
  button.disabled = true; status.textContent = 'Opening secure bank connection…';
  try {
    const response = await fetch('/api/finance/plaid/link-token'+(connectionId ? `?connection_id=${encodeURIComponent(connectionId)}` : ''), {method:'POST', credentials:'same-origin'});
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || 'Could not start Plaid Link');
    const temporaryToken = data.link_token;
    let handler;
    const cleanup = () => { try { handler?.destroy?.(); } catch (_) {} handler = null; };
    handler = window.Plaid.create({token: temporaryToken, onSuccess: async publicToken => {
      try {
        status.textContent = 'Finishing secure connection and syncing transactions…';
        const exchange = await fetch('/api/finance/plaid/link-exchange', {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body:JSON.stringify({public_token:publicToken, link_token:temporaryToken, authorization_state:data.authorization_state})});
        const result = await exchange.json().catch(()=>({}));
        if (!exchange.ok) throw Error(result.detail || 'Could not finish the connection');
        cleanup();
        await load(el);
      } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
        cleanup();
      }
    }, onExit: error => { status.textContent = error?.error_code ? 'Connection cancelled. No financial changes were made.' : 'Plaid connection closed.'; button.disabled=false; cleanup(); }});
    handler.open();
  } catch (error) { status.textContent = error.message; button.disabled = false; }
}

export function openIntegrationCenter(){const el=openView('integration-center',null,'Integration Center',loadingState());load(el);return el;}
registerView('integration-center',()=>openIntegrationCenter());
export default {openIntegrationCenter};
