import { openView, registerView } from './workspaceWindowManager.js';
import { errorState, loadingState, moduleHeader, statusBadge } from './ui-components.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function load(el) {
  const body = el.querySelector('.hades-window-body');
  body.innerHTML = loadingState('Loading Integration Center…');
  try {
    const [integrations, permissions] = await Promise.all([
      fetch('/api/setup-center/integrations', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Integration projection unavailable'); return data; }),
      fetch('/api/setup-center/permissions', {credentials:'same-origin'}).then(async response => { const data=await response.json(); if (!response.ok) throw Error(data.detail||'Authority projection unavailable'); return data; }),
    ]);
    const cards=(integrations.integrations||[]).map(item => `<article class="hades-record-card"><div><strong>${esc(item.title)}</strong><p>${esc(item.capabilities?.join(', ')||'No capabilities recorded')}</p><small>Last success: ${esc(item.last_success||'not recorded')} · secrets hidden</small></div><div>${statusBadge(item.connection,item.connection==='CONNECTED'?'success':item.connection==='DEGRADED'?'warning':'info')}</div></article>`).join('') || '<p class="muted">No canonical integrations are registered.</p>';
    body.innerHTML=`${moduleHeader({icon:'integrations',title:'Integration Center',description:'Connection health and capability readiness. Configure integrations in Setup Center or Settings; this view never exposes secrets.',primary:'Refresh',primaryId:'integration-center-refresh'})}<p class="muted">${esc((permissions.policy_source||'Canonical policy services remain authoritative.'))}</p><section class="setup-center-category"><h3>Connected integrations</h3><div class="hades-record-list">${cards}</div></section>`;
    body.querySelector('#integration-center-refresh').onclick=()=>load(el);
  } catch (error) { body.innerHTML=errorState(error.message,'integration-center-retry'); body.querySelector('#integration-center-retry')?.addEventListener('click',()=>load(el)); }
}

export function openIntegrationCenter(){const el=openView('integration-center',null,'Integration Center',loadingState());load(el);return el;}
registerView('integration-center',()=>openIntegrationCenter());
export default {openIntegrationCenter};
